import json
import argparse
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('--result', default='RESULT.json')
p.add_argument('--prefix', default='')
args = p.parse_args()
d = json.loads((root/args.result).read_text())
label = 'Phase-centered (t mod 5)' if 'preprocessing' in d else 'Raw'
fig, axes = plt.subplots(2, 4, figsize=(15, 8), constrained_layout=True)
for row, arm in enumerate(('native', 'forced')):
    for ax, rec in zip(axes[row], d['runs'][arm]['captures']):
        matrix = np.array(rec['cosine_matrix'], dtype=float)
        im = ax.imshow(matrix, origin='lower', cmap='coolwarm', vmin=-1, vmax=1,
                       interpolation='nearest', extent=(-.5, 30.5, -.5, 30.5))
        ax.plot([0,29], [0,29], 'k--', lw=.7)
        ax.axhspan(29.5,30.5,color='gray',alpha=.6)
        ax.axvspan(29.5,30.5,color='gray',alpha=.6)
        ax.set(title=f'{arm}; x0 step {rec["step_zero_based"]}',
               xlabel='Prediction difference index', ylabel='Reference difference index')
        ax.set_xticks([0,5,10,15,20,25,30]); ax.set_yticks([0,5,10,15,20,25,30])
fig.colorbar(im, ax=axes, label='Cosine similarity', shrink=.75)
fig.suptitle(label + ' R122 latent derivative similarity; gray row/column contains padding')
fig.savefig(root/(args.prefix+'similarity_matrices.png'), dpi=150)
plt.close(fig)

fig, axes = plt.subplots(2, 4, figsize=(15, 7), constrained_layout=True)
for col in range(4):
    for arm, color in (('native','tab:blue'),('forced','tab:orange')):
        rec = d['runs'][arm]['captures'][col]
        axes[0,col].plot([s['lag_bins'] for s in rec['lag_scores']],
                         [s['cosine_mean'] for s in rec['lag_scores']], 'o-',label=arm,color=color,ms=3)
        axes[1,col].plot(rec['activity_l2_per_second'],label=arm,color=color)
    axes[0,col].set(title=f'x0 step {rec["step_zero_based"]}',xlabel='Lag in position bins (+ = later prediction)',ylabel='Mean cosine, common 18 rows',ylim=(-.2,.65))
    axes[0,col].set_xticks(range(-6,7,2));axes[0,col].axvline(0,color='gray',lw=.7)
    axes[1,col].plot(d['reference']['activity_l2_per_second'],color='black',label='reference',lw=1)
    axes[1,col].axvspan(29.5,30.5,color='gray',alpha=.25)
    axes[1,col].set(xlabel='Temporal difference index',ylabel='L2 activity per second',xlim=(0,30))
axes[0,0].legend();axes[1,0].legend()
fig.suptitle(label + ' fixed lag scores and activity curves; full spatial grid')
fig.savefig(root/(args.prefix+'lag_and_activity.png'), dpi=150)
plt.close(fig)

fig,axes = plt.subplots(1,3,figsize=(13,4),constrained_layout=True)
for ax,key,title in zip(axes[:2],('reference_self','synthetic_feature_delay_3bins'),('Reference self','Synthetic feature delay +3 bins')):
    im=ax.imshow(np.array(d['controls'][key]['cosine_matrix'],float),origin='lower',cmap='coolwarm',vmin=-1,vmax=1)
    ax.set(title=title,xlabel='Prediction index',ylabel='Reference index')
    scores=d['controls'][key]['lag_scores']
    axes[2].plot([s['lag_bins'] for s in scores],[s['cosine_mean'] for s in scores],'o-',label=title)
axes[2].set(xlabel='Lag in bins',ylabel='Mean cosine',title='Analytical controls')
axes[2].legend(fontsize=8);fig.colorbar(im,ax=axes[:2],shrink=.7)
fig.suptitle(label + ': self comparison and synthetic shift after feature extraction')
fig.savefig(root/(args.prefix+'controls.png'),dpi=150)
plt.close(fig)
