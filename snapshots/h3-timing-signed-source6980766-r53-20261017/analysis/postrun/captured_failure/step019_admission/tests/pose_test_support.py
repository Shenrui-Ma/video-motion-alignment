"""Synthetic detector rows for current-state wrapper interface testing only."""
def row(window=(44,59),feature='arm_direction',lag=-5):
    comparison={str(c):{'proposal_lag':lag,'status':'measured','min_gain':.8,'null_comparisons':[
        {'null_lag':i,'proposal_cost':.1,'null_cost':.5,'gain':.8,'status':'valid'} for i in range(-2,3)]} for c in (.3,.5)}
    return {'window':list(window),'feature':feature,'status':'measured','baseline':'delayed_candidate' if lag>0 else 'advanced_candidate','min_gain':.8,'comparison':comparison}

def rows_for(tag,index):
    if tag=='off':return []
    if tag=='always':return [row((0,15),'left_arm_direction'),row((68,83),'right_arm_direction')]
    if tag=='restart':
        if index in (0,1,2):return [row((0,15),'left_arm_direction'),row((68,83),'right_arm_direction')]
        if index in (4,5):return [row()]
        if index>=6:return [row((68,83),'right_arm_direction',lag=5)]
        return []
    raise ValueError(tag)

def measurement(tag,index):
    return {'status':'complete','request_sha256':'synthetic','response_sha256':'synthetic',
        'observer':{'schema':'r27-whole-timeline-observation-v1','physical_index':index,'status':'measured','windows':rows_for(tag,index)}}

class OfflineObserver:
    def __init__(self,tag):self.tag=tag;self.calls=[]
    def __call__(self,state,row):
        n=row['physical_index'];assert row['branch']=='native' and len(state.transaction['branches'])==1
        self.calls.append(n);return measurement(self.tag,n)

class NoHistoricalGate:
    def begin(self,state,noise):pass
    def branch(self,state,x,output,row):pass
    def decision(self,state,index,decision):pass
    def finish(self,state):assert state.live_observer.calls==list(range(20))
TAGS=('off','restart','always')
