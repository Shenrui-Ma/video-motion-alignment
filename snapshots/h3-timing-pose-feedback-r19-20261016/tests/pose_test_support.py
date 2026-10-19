SCRIPTED={'prefix_only':[6,7,8,9],'always_late':list(range(6,20)),'reentry':[6,7,8,9,10,13,19]}
def measurement(lags,reasons=()):
 rows={t:{f:{'reliable_lag_frames':lags[i*2+j]} for i,f in enumerate(('arm_direction','wrist_relative'))} for j,t in enumerate(('0.3','0.5'))}
 return {'status':'complete','request_sha256':'synthetic','response_sha256':'synthetic','observer':{'diagnostics':{'50:65':rows},'observability':{'50:65':{'reasons':list(reasons),'automatic_intervention_authorized':False}}}}
class OfflineObserver:
 def __init__(self,mask):self.mask=mask;self.calls=[]
 def __call__(self,state,row):
  n=row['physical_index'];assert n>=10 and row['branch']=='native';assert len(state.transaction['branches'])==1
  self.calls.append(n)
  return measurement([4]*4 if n in self.mask else [-1]*4)
class NoHistoricalGate:
 def begin(self,state,noise):pass
 def branch(self,state,x,output,row):pass
 def finish(self,state):assert state.live_observer.calls==list(range(10,20))
