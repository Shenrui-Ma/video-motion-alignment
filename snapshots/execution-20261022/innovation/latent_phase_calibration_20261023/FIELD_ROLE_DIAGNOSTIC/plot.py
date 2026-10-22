"""Static scientific figures of recorded attention statistics, CPU only."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--summary',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    d=json.loads(args.summary.read_text());args.out.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.size':10,'svg.fonttype':'none','axes.spines.top':False,
                         'axes.spines.right':False,'figure.facecolor':'white'})
    colors=plt.get_cmap('tab10').colors[:5]
    titles=['Cabin | short_0252','Drinking | short_0358']
    fig,axs=plt.subplots(2,3,figsize=(15,8.2),layout='constrained')
    for row,(case,title) in enumerate(zip(d['cases'],titles)):
        s=case['post_anchor_steps_1_to_19'];x=np.arange(5);ax=axs[row,0]
        ax.bar(x-.18,s['raw_temporal_share']['mean_role_means'],.36,color=colors,alpha=.35,label='Before anchor')
        ax.bar(x+.18,s['normalized_temporal_share']['mean_role_means'],.36,color=colors,label='After anchor')
        ax.axhline(.5,color='#666666',ls=':',lw=.8)
        ax.set(xticks=x,xticklabels=[f'r{k}' for k in x],ylim=(0,.62),
               title=f'{title}\nTemporal-energy share',ylabel='Within-call role mean',xlabel='Absolute latent bin mod 5')
        ax.legend(frameon=False,fontsize=8)
        ax=axs[row,1]
        for k in range(5):
            ax.plot(range(20),[s['alpha']['mean_role_means'][k] for s in case['by_step']],color=colors[k],label=f'r{k}')
        ax.axhline(.25,color='#666666',ls=':',lw=.8)
        ax.set(xlim=(0,19),ylim=(.21,.28),title='Actual applied alpha',xlabel='Denoising forward (0-based)',ylabel='Mean across 50 layers')
        ax.legend(ncol=5,frameon=False,fontsize=8,loc='lower left')
        ax=axs[row,2]
        for metric,label,color in [('raw_temporal_share','Before anchor','#35669b'),
                                   ('normalized_temporal_share','After anchor','#df9a31'),
                                   ('alpha','Applied alpha','#35946e')]:
            vals=[s[metric]['within_call_ss_pooled_role_eta_squared'] for s in case['by_step']]
            ax.plot(range(20),[np.nan if v is None else v for v in vals],label=label,color=color)
        ax.set(xlim=(0,19),ylim=(0,1),title='Within-call role variance fraction',
               xlabel='Denoising forward (0-based)',ylabel='Descriptive between-role SS / total SS')
        ax.legend(frameon=False,fontsize=8)
    fig.suptitle('Posthoc attention-controller role diagnostics | two actual 20-step runs',fontsize=15)
    for suffix in ('svg','png'):fig.savefig(args.out/f'role_statistics.{suffix}',dpi=170)
    plt.close(fig)
    fig,axs=plt.subplots(2,1,figsize=(12,7),layout='constrained')
    for ax,case,title in zip(axs,d['cases'],titles):
        matrix=np.array([r['alpha_by_step'] for r in case['by_bin']]).T
        im=ax.imshow(matrix,origin='lower',aspect='auto',vmin=.18,vmax=.32,cmap='RdBu_r',interpolation='nearest')
        for t in range(5,case['bins'],5):ax.axvline(t-.5,color='white',lw=.8)
        for t in (0,case['bins']-1):
            ax.axvspan(t-.5,t+.5,facecolor='none',edgecolor='#333333',hatch='///',lw=.8)
        ax.set(title=f'{title}: actual alpha, averaged over 50 layers',xlabel='Absolute latent bin (all bins retained)',
               ylabel='Denoising forward',yticks=[0,5,10,15,19],xticks=list(range(0,case['bins'],2)))
    fig.colorbar(im,ax=axs,label='Actual alpha (endpoints hatched, fixed 0.25)',shrink=.9)
    for suffix in ('svg','png'):fig.savefig(args.out/f'alpha_by_bin.{suffix}',dpi=170)
    plt.close(fig)


if __name__=='__main__':main()
