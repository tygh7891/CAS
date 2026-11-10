"""A4 pure mock tests: no ROS imports, network access, or motor commands."""
import copy
from datetime import datetime
import json
from pathlib import Path
import unittest
from engine import Coordinator

ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/'scenario.mock.json').read_text())
REPORTS=[]

class ZoneCases(unittest.TestCase):
    def setUp(self):
        self.c=Coordinator(copy.deepcopy(CONFIG))
    def tearDown(self):
        REPORTS.append(dict(case=self._testMethodName,final=self.c.snapshot(),events=self.c.events))
    def step(self,n=1):
        for _ in range(n):
            self.c.tick(0.05)
            occupants=[r['id'] for r in self.c.robots.values() if self.c.overlaps(r['position'])]
            self.assertLessEqual(len(occupants),1)
            if occupants:self.assertEqual(occupants,[self.c.owner])
    def until(self,predicate,limit=500):
        for _ in range(limit):
            if predicate():return
            self.step()
        self.fail('Scenario did not reach expected precondition')
    def finish(self):
        self.until(lambda:self.c.finished)
    def grants(self,robot):
        return [e for e in self.c.events if e['event']=='ZONE_GRANTED' and e['robot_id']==robot]
    def in_zone(self):
        return self.c.owner=='robot_1' and self.c.overlaps(self.c.robots['robot_1']['position'])

    def test_01_simultaneous_requests_are_serialized(self):
        """동시 요청: 1번 이탈 확인 후 2번 허가"""
        self.finish()
        self.assertTrue(all(r['task_state']=='SUCCEEDED' for r in self.c.robots.values()))
        e=self.c.events
        release=next(i for i,v in enumerate(e) if v['event']=='ZONE_RELEASED' and v['robot_id']=='robot_1')
        grant=next(i for i,v in enumerate(e) if v['event']=='ZONE_GRANTED' and v['robot_id']=='robot_2')
        self.assertLess(release,grant)
        self.assertIsNone(self.c.owner)

    def test_02_cancel_before_entry_releases_after_mock_ack(self):
        """진입 전 취소: 모의 정지·영역 밖 확인 후 예약 해제"""
        self.until(lambda:self.c.owner=='robot_1')
        self.assertFalse(self.c.overlaps(self.c.robots['robot_1']['position']))
        self.c.cancel_robot('robot_1')
        self.assertIsNone(self.c.owner)
        self.finish()
        self.assertEqual(self.c.robots['robot_1']['task_state'],'CANCELED')
        self.assertEqual(self.c.robots['robot_2']['task_state'],'SUCCEEDED')

    def test_03_cancel_inside_keeps_lock_and_other_robot_waiting(self):
        """점유 중 취소: 권한 유지·2번 대기"""
        self.until(self.in_zone)
        position=list(self.c.robots['robot_1']['position'])
        self.c.cancel_robot('robot_1');self.step(100)
        self.assertEqual(self.c.owner,'robot_1')
        self.assertEqual(self.c.robots['robot_1']['position'],position)
        self.assertEqual(self.c.robots['robot_2']['phase'],'WAITING_ZONE')
        self.assertFalse(self.grants('robot_2'))
        self.assertIsNotNone(self.c.blocked_reason)

    def test_04_cancel_waiter_removes_queued_request(self):
        """대기 로봇 취소: 대기열 제거·허가 없음"""
        self.until(lambda:'robot_2' in self.c.waiting)
        self.c.cancel_robot('robot_2')
        self.assertNotIn('robot_2',self.c.waiting)
        self.finish()
        self.assertEqual(self.c.robots['robot_1']['task_state'],'SUCCEEDED')
        self.assertFalse(self.grants('robot_2'))

    def test_05_failure_in_zone_halts_without_handoff(self):
        """점유 중 실패: 전체 모의 진행 보류·권한 유지"""
        self.until(self.in_zone)
        self.c.fail_all('Injected mock navigation failure');self.step(60)
        self.assertEqual(self.c.owner,'robot_1')
        self.assertTrue(all(r['task_state']=='FAILED' for r in self.c.robots.values()))
        self.assertFalse(self.grants('robot_2'))

    def test_06_position_loss_inside_blocks_handoff(self):
        """점유 중 위치 갱신 중단: 1초 경과 시 보류·해제 없음"""
        self.until(self.in_zone)
        self.c.set_feedback('robot_1',False);self.step(25)
        self.assertTrue(self.c.canceled)
        self.assertIn('Pose stale',self.c.blocked_reason)
        self.assertEqual(self.c.owner,'robot_1')
        self.assertFalse(self.grants('robot_2'))

    def test_07_position_loss_near_exit_cannot_release(self):
        """이탈 직전 위치 중단: 가상 본체가 나가도 오래된 관측으로 해제 금지"""
        self.until(lambda:self.c.owner=='robot_1' and self.c.robots['robot_1']['position'][0]>0.1)
        self.assertTrue(self.c.overlaps(self.c.robots['robot_1']['position']))
        self.c.set_feedback('robot_1',False);self.step(30)
        self.assertFalse(self.c.overlaps(self.c.robots['robot_1']['position']))
        self.assertTrue(self.c.overlaps(self.c.robots['robot_1']['observed_position']))
        self.assertEqual(self.c.owner,'robot_1')
        self.assertFalse(self.grants('robot_2'))

    def test_08_old_feedback_replay_does_not_refresh_pose(self):
        """캐시 위치 재전송: 원본 시각이 같으면 최신으로 처리하지 않음"""
        self.until(self.in_zone)
        r=self.c.robots['robot_1'];stamp=r['pose_time'];position=list(r['observed_position'])
        self.c.set_feedback('robot_1',False)
        for _ in range(25):
            self.assertFalse(self.c.report_pose('robot_1',position,stamp));self.step()
        self.assertEqual(r['pose_time'],stamp)
        self.assertTrue(self.c.canceled)
        self.assertFalse(self.grants('robot_2'))

    def test_09_feedback_recovery_does_not_auto_restart(self):
        """갱신 복구 후에도 자동 재출발·잠금 해제 없음"""
        self.until(self.in_zone)
        self.c.set_feedback('robot_1',False);self.step(25)
        frozen=[list(r['position']) for r in self.c.robots.values()]
        self.c.set_feedback('robot_1',True);self.step(50)
        self.assertEqual(frozen,[r['position'] for r in self.c.robots.values()])
        self.assertEqual(self.c.owner,'robot_1')
        self.assertFalse(self.grants('robot_2'))

    def test_10_duplicate_requests_do_not_duplicate_queue(self):
        """중복 진입 요청: 대기열 중복·중복 허가 없음"""
        self.until(lambda:'robot_2' in self.c.waiting)
        for _ in range(5):self.assertFalse(self.c.request_zone('robot_2'))
        self.assertEqual(self.c.waiting.count('robot_2'),1)
        self.finish()
        self.assertEqual(len(self.grants('robot_2')),1)

    def test_11_cancel_completed_task_is_noop(self):
        """완료 후 취소 재요청: 완료 결과·권한 변경 없음"""
        self.finish();events=len(self.c.events)
        self.c.cancel_robot('robot_1');self.c.cancel_robot('robot_1')
        self.assertEqual(self.c.robots['robot_1']['task_state'],'SUCCEEDED')
        self.assertEqual(len(self.c.events),events)
        self.assertIsNone(self.c.owner)

    def test_12_tie_break_uses_robot_id_not_config_order(self):
        """설정 순서가 달라도 동률은 1번 우선"""
        config=copy.deepcopy(CONFIG);config['robots'].reverse();self.c=Coordinator(config)
        self.until(lambda:self.c.owner is not None)
        self.assertEqual(self.c.owner,'robot_1')

if __name__=='__main__':
    print('CAS A4 | 12 mock cases | NO ROS / NO NETWORK / NO MOTOR COMMANDS',flush=True)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ZoneCases)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    path=ROOT/'logs'/('a4_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json')
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,cases=REPORTS),ensure_ascii=False,indent=2))
    print('LOG: '+str(path),flush=True)
    print('A4 ALL PASSED (MOCK ONLY)' if result.wasSuccessful() else 'A4 FAILED',flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)
