"""Read-only ROS map metadata and pixel/map transforms. No navigation commands."""
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re
import yaml

@dataclass(frozen=True)
class MapSpec:
    yaml_path: str
    image_path: str
    width: int
    height: int
    resolution: float
    origin: tuple
    negate: int
    occupied_thresh: float
    free_thresh: float
    mode: str
    digest: str

    def image_to_world(self,u,v):
        # Continuous image coordinates: (0,0) is the top-left image edge.
        x=u*self.resolution;y=(self.height-v)*self.resolution
        ox,oy,yaw=self.origin;c=math.cos(yaw);s=math.sin(yaw)
        return ox+c*x-s*y,oy+s*x+c*y

    def world_to_image(self,x,y):
        ox,oy,yaw=self.origin;c=math.cos(yaw);s=math.sin(yaw)
        dx=x-ox;dy=y-oy
        return (c*dx+s*dy)/self.resolution,self.height-(-s*dx+c*dy)/self.resolution

    def pixel_center(self,column,row):
        if not (0<=column<self.width and 0<=row<self.height):raise ValueError('Pixel outside map')
        return self.image_to_world(column+0.5,row+0.5)

    def metadata(self):
        return dict(yaml_path=self.yaml_path,image_path=self.image_path,width=self.width,height=self.height,
                    resolution=self.resolution,origin=list(self.origin),negate=self.negate,
                    occupied_thresh=self.occupied_thresh,free_thresh=self.free_thresh,mode=self.mode,
                    sha256=self.digest,corners=[list(self.image_to_world(u,v)) for u,v in [(0,0),(self.width,0),(self.width,self.height),(0,self.height)]])

def load_map(path):
    path=Path(path).expanduser().resolve()
    raw=path.read_bytes();data=yaml.safe_load(raw)
    if not isinstance(data,dict):raise ValueError('Map YAML must be an object')
    image_value=data.get('image')
    if not isinstance(image_value,str) or not image_value:raise ValueError('Map image is missing')
    image=(path.parent/image_value).resolve();pixels=image.read_bytes()
    # B1 supports supplied P2/P5 PGM files; reject uninspected image types explicitly.
    header=re.findall(rb'[^\s#]+|#[^\r\n]*',pixels)
    tokens=[x for x in header if not x.startswith(b'#')]
    if len(tokens)<4 or tokens[0] not in (b'P2',b'P5'):raise ValueError('B1 expects a PGM P2/P5 image')
    width,height,maximum=map(int,tokens[1:4])
    if not (0<width<=10000 and 0<height<=10000 and 1<=maximum<=65535):raise ValueError('Invalid PGM dimensions')
    resolution=float(data['resolution']);origin=tuple(float(v) for v in data['origin'])
    if len(origin)!=3 or not all(math.isfinite(v) for v in origin):raise ValueError('Invalid origin')
    if not math.isfinite(resolution) or resolution<=0:raise ValueError('Invalid resolution')
    negate=data.get('negate',0);free=float(data.get('free_thresh',0.196));occupied=float(data.get('occupied_thresh',0.65))
    if negate not in (0,1) or not 0<=free<occupied<=1:raise ValueError('Invalid map thresholds')
    mode=data.get('mode','trinary')
    if mode not in ('trinary','scale','raw'):raise ValueError('Invalid map mode')
    return MapSpec(str(path),str(image),width,height,resolution,origin,negate,occupied,free,mode,
                   hashlib.sha256(raw+b'\0'+pixels).hexdigest())

def review_maps(path,mask_path=None):
    base=load_map(path);mask=load_map(mask_path) if mask_path else None
    if mask:
        if (base.width,base.height)!=(mask.width,mask.height):raise ValueError('Mask dimensions differ from map')
        if abs(base.resolution-mask.resolution)>1e-10 or any(abs(a-b)>1e-10 for a,b in zip(base.origin,mask.origin)):
            raise ValueError('Mask coordinates differ from map')
    return dict(base=base.metadata(),mask=mask.metadata() if mask else None,
                mask_usage='DISPLAY_ONLY_UNCONFIRMED',coordinates_confirmed=False)
