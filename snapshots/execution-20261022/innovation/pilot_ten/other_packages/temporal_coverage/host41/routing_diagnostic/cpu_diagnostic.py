"""CPU-only synthetic reproduction. No Q/K capture exists for historical pilots."""
import json,time,torch
from pathlib import Path
torch.set_num_threads(1);torch.manual_seed(20261022)
def solve(q,iterations):
 n=len(q);i=torch.arange(n,dtype=q.dtype);support=(i[:,None]-i[None,:]).abs()<=2
 rowmax=q.masked_fill(~support,-torch.inf).max(-1).values
 logk=((q-rowmax[:,None]-.25*(i[:,None]-i[None,:]).square())/.5).masked_fill(~support,-torch.inf)
 v=torch.zeros(n,dtype=q.dtype);started=time.perf_counter()
 for _ in range(iterations):
  u=-torch.logsumexp(logk+v[None,:],dim=1);v=-torch.logsumexp(logk+u[:,None],dim=0)
 p=(logk+u[:,None]+v[None,:]).exp();before_rows=float((p.sum(1)-1).abs().max());before_cols=float((p.sum(0)-1).abs().max())
 p=p/p.sum(-1,keepdim=True);err=(p.sum(0)-1).abs()
 return {'iterations':iterations,'dtype':str(q.dtype),'seconds':time.perf_counter()-started,'before_final_row_normalize_row_error':before_rows,'before_final_row_normalize_column_error':before_cols,'after_column_error':float(err.max()),'worst_column':int(err.argmax()),'first_last_errors':[float(err[0]),float(err[-1])],'passed_2e4':float(err.max())<=.0002}
out=[]
for n in (5,29,32):
 t=torch.arange(n,dtype=torch.float64)
 qs={'column_bias':.325*t[None,:].repeat(n,1),'varying_column_bias':.325*t[None,:].repeat(n,1)+.25*torch.randn(n,n,dtype=torch.float64),'random':.6*torch.randn(n,n,dtype=torch.float64)}
 for kind,q in qs.items():
  span=(q.masked_fill((t[:,None]-t[None,:]).abs()>2,-torch.inf).max(-1).values-q.masked_fill((t[:,None]-t[None,:]).abs()>2,torch.inf).min(-1).values).mean().item()
  rows=[]
  for dtype in (torch.float32,torch.float64):
   for iterations in (128,512,2048):rows.append(solve(q.to(dtype),iterations))
  out.append({'bins':n,'synthetic_kind':kind,'mean_span':span,'results':rows})
print(json.dumps({'device':'cpu','actual_quality_matrices_available':False,'tests':out},indent=2))
