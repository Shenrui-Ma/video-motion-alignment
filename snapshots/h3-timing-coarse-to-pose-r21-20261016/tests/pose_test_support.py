SCRIPTED={'all_off':[],'all_on':list(range(6,20)),'reentry':[6,7,11,15,17,19]}
EARLY={'all_off':[24,-1,-1,-1,-1],'all_on':[-1,4,4,4,4],'reentry':[24,4,3,0,3]}
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
 def decision(self,state,n,decision):pass
 def finish(self,state):assert state.live_observer.calls==list(range(10,20))
