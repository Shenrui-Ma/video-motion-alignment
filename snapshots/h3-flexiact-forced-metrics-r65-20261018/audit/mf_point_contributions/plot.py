"""Standalone scientific point-score maps from an existing CPU decomposition."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['MPLBACKEND']='Agg'
import argparse,csv,json,subprocess
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

def main(root):
    out=Path(__file__).resolve().parent
    result=json.loads((out/'fitness_contributions.json').read_text())
    assert result['initial_grid_coordinates_exactly_equal'] is True
    images={}
    for method in ('native','forced'):
        image=out/f'{method}_frame0.png'
        subprocess.run(['ffmpeg','-v','error','-nostdin','-n','-threads','2','-i',str(root/'incoming/fitness'/f'{method}.mp4'),'-frames:v','1',str(image)],check=True,timeout=30)
        images[method]=np.asarray(Image.open(image).convert('RGB'))
        assert images[method].shape[:2]==(768,1152)
    delta=np.asarray(result['delta']); limit=float(np.abs(delta).max())
    fig,axes=plt.subplots(3,2,figsize=(16,17),layout='constrained')
    for col,method in enumerate(('native','forced')):
        xy=np.asarray(result['rows'][method]['xy']); score=np.asarray(result['rows'][method]['point_score'])
        for row in range(3):
            ax=axes[row,col]; ax.imshow(images[method],alpha=1 if row==0 else .65)
            ax.set_xlim(0,1152);ax.set_ylim(768,0);ax.axis('off')
        axes[0,col].set_title(f'{method.capitalize()}: actual first frame',fontsize=16)
        points=axes[1,col].scatter(xy[:,0],xy[:,1],c=score,s=9,cmap='viridis',vmin=-1,vmax=1,linewidths=0)
        axes[1,col].set_title(f'Official per-point score; mean={score.mean():.4f}',fontsize=15)
        diff=axes[2,col].scatter(xy[:,0],xy[:,1],c=delta,s=9,cmap='RdBu_r',vmin=-limit,vmax=limit,linewidths=0)
        axes[2,col].set_title(f'Forced minus Native, on {method} frame',fontsize=15)
    fig.colorbar(points,ax=axes[1,:],fraction=.025,pad=.01,label='s_i = max_j(M_ij - identity_ij)')
    fig.colorbar(diff,ax=axes[2,:],fraction=.025,pad=.01,label='Delta s_i (same 3025 initial query locations)')
    fig.suptitle('Fitness: spatial distribution of official MF point scores\nWhole-video trajectory score attached to its initial grid location; no foreground mask',fontsize=18)
    fig.savefig(out/'fitness_mf_point_maps.png',dpi=160)
    fig.savefig(out/'fitness_mf_point_maps.pdf')
    plt.close(fig)
    with (out/'fitness_point_scores.csv').open('x',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['point_index','initial_x','initial_y','native_score','forced_score','forced_minus_native'])
        for i,(xy,n,f,d) in enumerate(zip(result['rows']['native']['xy'],result['rows']['native']['point_score'],result['rows']['forced']['point_score'],result['delta'])):
            writer.writerow([i,*xy,n,f,d])
    print(out/'fitness_mf_point_maps.png')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();main(a.root)
