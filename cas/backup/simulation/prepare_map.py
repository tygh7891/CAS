"""Map-derived collision world and conservative candidates; offline only."""
import argparse
from pathlib import Path
import json
import math
import sys
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
import yaml
from prepare import prepare,world_tree
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'operator_app'))
from map_geometry import load_map,review_maps

RADIUS=0.10
CLEARANCE=0.12

def rectangles(binary):
    """Exact nonoverlapping pixel rectangles; no wall dilation/smoothing."""
    active={};result=[]
    for row,line in enumerate(np.asarray(binary,dtype=bool)):
        starts=np.flatnonzero(np.diff(np.r_[False,line,False].astype(int))==1)
        ends=np.flatnonzero(np.diff(np.r_[False,line,False].astype(int))==-1)
        runs=set(zip(starts.tolist(),ends.tolist()))
        for key in list(active):
            if key not in runs:
                result.append((*key,active.pop(key),row))
        for key in runs:
            if key not in active:active[key]=row
    for key,start in active.items():result.append((*key,start,len(binary)))
    return sorted(result)

def arrays(map_path,mask_path):
    review_maps(map_path,mask_path)
    spec=load_map(map_path)
    if spec.mode!='trinary':raise ValueError('Map world requires trinary input')
    raw=np.array(Image.open(spec.image_path).convert('L'))
    brightness=raw/255.0
    occupancy=brightness if spec.negate else 1-brightness
    occupied=occupancy>=spec.occupied_thresh
    free=occupancy<=spec.free_thresh
    mask=load_map(mask_path)
    mask_raw=np.array(Image.open(mask.image_path).convert('L'))
    if not np.isin(mask_raw,[0,255]).all():raise ValueError('Allowed mask must be binary 0/255 for this profile')
    # User confirmed raw white means allowed. Do not invert it.
    allowed=(mask_raw==255)&free
    return spec,occupied,allowed

def candidate_layout(spec,allowed):
    clearance=distance_transform_edt(np.pad(allowed,1,constant_values=False))[1:-1,1:-1]*spec.resolution
    h,w=allowed.shape
    yy,xx=np.indices(allowed.shape)
    diagonal_a=allowed & (((xx<w*.4)&(yy<h*.4))|((xx>w*.6)&(yy>h*.6)))
    diagonal_b=allowed & (((xx>w*.6)&(yy<h*.4))|((xx<w*.4)&(yy>h*.6)))
    if min(int(diagonal_a.sum()),int(diagonal_b.sum()))<20:raise ValueError('X arms not sufficiently identified')
    slope_a,intercept_a=np.polyfit(xx[diagonal_a],yy[diagonal_a],1)
    slope_b,intercept_b=np.polyfit(xx[diagonal_b],yy[diagonal_b],1)
    if abs(slope_a-slope_b)<.1:raise ValueError('X crossing could not be estimated')
    crossing_x=(intercept_b-intercept_a)/(slope_a-slope_b)
    crossing_y=slope_a*crossing_x+intercept_a
    col,row=int(round(crossing_x)),int(round(crossing_y))
    if not (abs(col-w/2)<w*.14 and abs(row-h/2)<h*.14):raise ValueError('Crossing candidate outside central region')
    if clearance[row,col]<CLEARANCE:raise ValueError('No sufficiently clear central crossing candidate')
    center=np.array(spec.pixel_center(col,row))
    def clear_segment(a,b):
        for t in np.linspace(0,1,1001):
            u,v=spec.world_to_image(*(a+(b-a)*t));c,r=math.floor(u),math.floor(v)
            if not (0<=r<h and 0<=c<w and clearance[r,c]>=RADIUS+.005):return False
        return True
    points={}
    for name,quadrant in [('A',(xx<w/2)&(yy<h/2)),('B',(xx>=w/2)&(yy<h/2)),('1',(xx<w/2)&(yy>=h/2)),('2',(xx>=w/2)&(yy>=h/2))]:
        valid=quadrant & (clearance>=CLEARANCE)
        distance=(xx-col)**2+(yy-row)**2
        if not valid.any():raise ValueError('No safe candidate for '+name)
        choices=np.argwhere(valid)
        ordered=sorted(choices,key=lambda rc: (-distance[rc[0],rc[1]],-clearance[rc[0],rc[1]],int(rc[0]),int(rc[1])))
        chosen=None
        for y,x in ordered:
            wx,wy=spec.pixel_center(int(x),int(y))
            if clear_segment(np.array([wx,wy]),center):chosen=(int(y),int(x),wx,wy);break
        if chosen is None:raise ValueError('No footprint-clear candidate route for '+name)
        y,x,wx,wy=chosen
        points[name]=dict(x=wx,y=wy,pixel=[int(x),int(y)],clearance_m=float(clearance[y,x]))
    half=.15
    # Zone aligned with map image axes, then rotated into world frame.
    yaw=spec.origin[2];rotation=np.array([[math.cos(yaw),-math.sin(yaw)],[math.sin(yaw),math.cos(yaw)]])
    polygon=[(center+rotation@np.array([x,y])).tolist() for x,y in [(-half,-half),(half,-half),(half,half),(-half,half)]]
    waits={}
    for robot,start in [('robot_1','1'),('robot_2','2')]:
        s=np.array([points[start]['x'],points[start]['y']]);valid=[]
        for t in np.linspace(0,1,201):
            p=s+(center-s)*t;local=rotation.T@(p-center)
            distance=math.hypot(max(abs(local[0])-half,0),max(abs(local[1])-half,0))
            u,v=spec.world_to_image(*p);c,r=math.floor(u),math.floor(v)
            if 0<=r<h and 0<=c<w and clearance[r,c]>=CLEARANCE and distance>RADIUS+.02:valid.append(p)
        if not valid:raise ValueError('No valid waiting candidate')
        p=valid[-1];waits[robot]=dict(x=float(p[0]),y=float(p[1]))
    for start,goal in [('1','B'),('2','A')]:
        a=np.array([points[start]['x'],points[start]['y']]);b=np.array([points[goal]['x'],points[goal]['y']])
        if not clear_segment(a,center) or not clear_segment(center,b):
            raise ValueError(f'Candidate route {start}->center->{goal} lacks footprint clearance; manual planning needed')
    return dict(schema_version=1,status='CANDIDATES_NOT_APPROVED',coordinates_confirmed=False,map_sha256=spec.digest,
                mask_semantics='RAW_WHITE_ALLOWED',center_method='two-diagonal least-squares intersection; unapproved',robot_radius_with_margin_m=RADIUS,candidate_min_clearance_m=CLEARANCE,
                points=points,waiting=waits,shared_zone=dict(center=center.tolist(),polygon=polygon),
                note='Candidate geometry only. No Nav2 path/rotation/inertia validation. No job execution allowed.')

def add_geometry(world,spec,occupied,allowed,candidates):
    for model in list(world.findall('model')):world.remove(model)
    world.set('name','cas_map_profile')
    def model(name):
        m=ET.SubElement(world,'model',name=name);ET.SubElement(m,'static').text='true'
        return ET.SubElement(m,'link',name='body')
    def box(link,name,pose,size,color,collision=True):
        for kind in (['collision','visual'] if collision else ['visual']):
            e=ET.SubElement(link,kind,name=name+'_'+kind);ET.SubElement(e,'pose').text=' '.join(map(str,pose))
            geometry=ET.SubElement(e,'geometry');b=ET.SubElement(geometry,'box');ET.SubElement(b,'size').text=' '.join(map(str,size))
            if kind=='visual':
                material=ET.SubElement(e,'material');ET.SubElement(material,'ambient').text=color;ET.SubElement(material,'diffuse').text=color
    cx,cy=spec.image_to_world(spec.width/2,spec.height/2);yaw=spec.origin[2]
    box(model('map_floor'),'floor',[cx,cy,-.025,0,0,yaw],[spec.width*spec.resolution+.1,spec.height*spec.resolution+.1,.05],'0.9 0.9 0.9 1')
    walls=model('map_occupied_cells')
    for i,(x0,x1,y0,y1) in enumerate(rectangles(occupied)):
        x,y=spec.image_to_world((x0+x1)/2,(y0+y1)/2)
        box(walls,f'wall_{i}',[x,y,.15,0,0,yaw],[(x1-x0)*spec.resolution,(y1-y0)*spec.resolution,.3],'0.3 0.35 0.4 1')
    lane=model('allowed_lane_visual_only')
    for i,(x0,x1,y0,y1) in enumerate(rectangles(allowed)):
        x,y=spec.image_to_world((x0+x1)/2,(y0+y1)/2)
        box(lane,f'lane_{i}',[x,y,.001,0,0,yaw],[(x1-x0)*spec.resolution,(y1-y0)*spec.resolution,.001],'0.25 0.7 0.85 1',False)
    zone=model('shared_zone_candidate_visual_only');x,y=candidates['shared_zone']['center']
    box(zone,'zone',[x,y,.003,0,0,yaw],[.3,.3,.001],'0.95 0.75 0.15 1',False)
    return len(rectangles(occupied))

def prepare_map(output,map_path,mask_path):
    output=Path(output).expanduser().resolve();output.mkdir(parents=True,exist_ok=True)
    spec,occupied,allowed=arrays(map_path,mask_path);candidates=candidate_layout(spec,allowed)
    # With negate=0: white free, black blocked. Combine lane policy with real/unknown map cells.
    Image.fromarray(np.where(allowed,255,0).astype(np.uint8)).save(output/'nav2_keepout_draft.pgm')
    metadata=dict(image='nav2_keepout_draft.pgm',mode='trinary',resolution=spec.resolution,origin=list(spec.origin),negate=0,occupied_thresh=.65,free_thresh=.196)
    (output/'nav2_keepout_draft.yaml').write_text(yaml.safe_dump(metadata,sort_keys=False))
    (output/'scenario.candidates.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2))
    stats={}
    def build():
        root,world=world_tree();stats['wall_rectangles']=add_geometry(world,spec,occupied,allowed,candidates);return root,world
    poses=[]
    for robot,start,target in [('robot_1','1','B'),('robot_2','2','A')]:
        a=candidates['points'][start];b=candidates['points'][target];yaw=math.atan2(b['y']-a['y'],b['x']-a['x'])
        poses.append((robot,f"{a['x']} {a['y']} 0.02 0 0 {yaw}"))
    prepare(output,world_builder=build,spawn_poses=poses)
    stats.update(occupied_pixels=int(occupied.sum()),allowed_pixels=int(allowed.sum()),map_sha256=spec.digest,
                 source_map=str(Path(map_path).resolve()),source_allowed_mask=str(Path(mask_path).resolve()),wall_height_m=.3,
                 physical_world_from='occupied cells only; internal forbidden regions have no collision geometry',
                 nav2_keepout_applied=False)
    (output/'map_profile_report.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2))
    print(json.dumps(stats,ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);parser.add_argument('--map',required=True);parser.add_argument('--mask',required=True)
    args=parser.parse_args();prepare_map(args.output,args.map,args.mask)
