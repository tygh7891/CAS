"""Read-only base map and optional raw mask visualization for B1."""
import math
from PyQt5.QtCore import Qt,QPointF,QRectF
from PyQt5.QtGui import QColor,QImage,QPainter,QPen
from PyQt5.QtWidgets import QWidget
from map_geometry import load_map

class ReceivedMapView(QWidget):
    def __init__(self):
        super().__init__();self.setMinimumSize(380,300);self.spec=None;self.mask=None
        self.image=None;self.overlay=None;self.key=None;self.show_mask=False;self.selected=None
        self.image_error=None;self.on_point=None;self.state=None;self.candidates=None
    def set_review(self,review):
        self.candidates=review.get('candidates')
        key=(review['base']['sha256'],review['mask']['sha256'] if review['mask'] else None)
        if key==self.key:return
        self.spec=load_map(review['base']['yaml_path'])
        self.image=QImage(self.spec.image_path);self.image_error=None
        if self.image.isNull():self.image_error='지도 이미지를 읽지 못했습니다.'
        elif (self.image.width(),self.image.height())!=(self.spec.width,self.spec.height):self.image_error='지도 이미지 크기가 메타데이터와 다릅니다.'
        self.mask=load_map(review['mask']['yaml_path']) if review['mask'] else None
        self.overlay=None
        if self.mask:
            raw=QImage(self.mask.image_path)
            if raw.isNull():self.image_error='마스크 이미지를 읽지 못했습니다.'
            else:
                self.overlay=QImage(raw.size(),QImage.Format_ARGB32);self.overlay.fill(Qt.transparent)
                for y in range(raw.height()):
                    for x in range(raw.width()):
                        if raw.pixelColor(x,y).lightness()>127:self.overlay.setPixelColor(x,y,QColor(0,160,200,100))
        self.key=key;self.selected=None;self.update()
    def image_rect(self):
        if not self.spec:return QRectF()
        scale=min((self.width()-40)/self.spec.width,(self.height()-60)/self.spec.height)
        width=self.spec.width*scale;height=self.spec.height*scale
        return QRectF((self.width()-width)/2,(self.height()-height)/2,width,height)
    def mousePressEvent(self,event):
        if self.spec is None or self.image_error:return
        rect=self.image_rect();pos=QPointF(event.pos())
        if not rect.contains(pos):return
        u=(pos.x()-rect.left())/rect.width()*self.spec.width
        v=(pos.y()-rect.top())/rect.height()*self.spec.height
        col,row=math.floor(u),math.floor(v)
        if not(0<=col<self.spec.width and 0<=row<self.spec.height):return
        self.selected=(col,row);x,y=self.spec.pixel_center(col,row)
        value=self.image.pixelColor(col,row).lightness()
        if self.on_point:self.on_point(f'픽셀 ({col}, {row}) 중심 → map: x={x:.3f}m, y={y:.3f}m · 명도 {value} (목표 지정 아님)')
        self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#f5f7fb'))
        p.setPen(QColor('#475569'))
        if self.spec is None:p.drawText(self.rect(),Qt.AlignCenter,'지도 로딩 대기');return
        if self.image_error:p.drawText(self.rect(),Qt.AlignCenter,self.image_error);return
        rect=self.image_rect();p.drawImage(rect,self.image)
        if self.show_mask and self.overlay is not None:p.drawImage(rect,self.overlay)
        p.setPen(QPen(QColor('#64748b'),1));p.setBrush(Qt.NoBrush);p.drawRect(rect)
        if self.selected:
            col,row=self.selected
            point=QPointF(rect.left()+(col+.5)/self.spec.width*rect.width(),rect.top()+(row+.5)/self.spec.height*rect.height())
            p.setPen(QPen(QColor('#dc2626'),2));p.drawLine(point+QPointF(-9,0),point+QPointF(9,0));p.drawLine(point+QPointF(0,-9),point+QPointF(0,9))
        if self.candidates:
            def screen(x,y):
                u,v=self.spec.world_to_image(x,y)
                return QPointF(rect.left()+u/self.spec.width*rect.width(),rect.top()+v/self.spec.height*rect.height())
            from PyQt5.QtGui import QPolygonF
            sim_mode=bool(self.state and self.state.get('mode')=='SIM_NAV2')
            if sim_mode:
                routes=self.state.get('layout',{}).get('routes',{})
                for name,legs in routes.items():
                    pen_color=QColor('#3b82f6' if name=='robot_1' else '#f59e0b')
                    pen_color.setAlpha(150)
                    p.setPen(QPen(pen_color,2,Qt.SolidLine))
                    for leg in legs:
                        for a,b in zip(leg,leg[1:]):
                            p.drawLine(screen(*a),screen(*b))
            polygon=QPolygonF([screen(*xy) for xy in self.candidates['shared_zone']['polygon']])
            zone_state=self.state.get('zone',{}) if sim_mode else {}
            if zone_state.get('blocked_reason'):
                p.setPen(QPen(QColor('#dc2626'),2,Qt.DashLine));p.setBrush(QColor(254,202,202,120))
            elif zone_state.get('owner'):
                p.setPen(QPen(QColor('#16a34a'),2,Qt.DashLine));p.setBrush(QColor(187,247,208,110))
            else:
                p.setPen(QPen(QColor('#ca8a04'),2,Qt.DashLine));p.setBrush(QColor(255,220,0,65))
            p.drawPolygon(polygon)
            p.setBrush(Qt.NoBrush)
            suffix='' if sim_mode else ' 후보'
            for name,point in self.candidates['points'].items():
                center=screen(point['x'],point['y']);p.setPen(QPen(QColor('#1d4ed8'),2));p.drawEllipse(center,6,6);p.drawText(center+QPointF(8,-6),name+suffix)
            for name,point in self.candidates['waiting'].items():
                center=screen(point['x'],point['y']);p.setPen(QPen(QColor('#b45309'),2));p.drawEllipse(center,4,4);p.drawText(center+QPointF(6,14),'W'+name[-1])
            if sim_mode:
                colors={'robot_1':'#2563eb','robot_2':'#d97706'}
                for r in self.state.get('simulation',{}).get('robots',[]):
                    pos=r.get('position')
                    if r.get('pose_valid') is False or not pos or len(pos)!=2:continue
                    center=screen(pos[0],pos[1]);color=QColor(colors.get(r['id'],'#2563eb'))
                    p.setPen(QPen(Qt.white,2));p.setBrush(color);p.drawEllipse(center,10,10)
                    angle=float(r.get('yaw',0.0))
                    tip=screen(pos[0]+0.09*math.cos(angle),pos[1]+0.09*math.sin(angle))
                    p.setPen(QPen(Qt.white,2));p.drawLine(center,tip)
                    p.setPen(color);p.drawText(center+QPointF(12,5),r['id'].replace('robot_','R'))
        p.setPen(QColor('#334155'))
        p.drawText(10,18,'Gazebo SIM_NAV2 · 검증 경로 및 실시간 TF 위치 표시 (도메인 84)' if (self.state and self.state.get('mode')=='SIM_NAV2') else '수령 지도 · 좌표 후보는 미승인 / 주행 불가')
        p.setPen(QColor('#64748b'));p.drawText(10,self.height()-10,'상단이 이미지 row=0 · 클릭: 픽셀 중심의 map 좌표 확인')
