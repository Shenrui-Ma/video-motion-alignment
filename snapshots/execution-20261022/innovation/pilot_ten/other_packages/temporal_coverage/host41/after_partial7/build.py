from pathlib import Path
import json,sys
P=Path(__file__).resolve().parent;H=P.parent;E=H.parents[4];A=E/'supervision/innovation_handoff';PART=E/'innovation/pilot_ten/other_packages/partial_temporal_rope/host41'
sys.path.insert(0,str(A));import activate_direction_pilots as activation
req=json.loads((H/'handoff_request.json').read_text());req['base']=json.loads((P/'base_manifest43.json').read_text());req['prerequisite_ids']=[j['id'] for j in req['base']['jobs'] if j['metadata'].get('method')=='partial_temporal_rope'];assert len(req['base']['jobs'])==43 and len(req['prerequisite_ids'])==7
cancel={j['id'] for j in json.loads((P/'receipt.json').read_text())['cancelled_jobs']};assert not cancel.intersection(j['id'] for j in req['base']['jobs']);assert len(req['pilots']['jobs'])==2
(P/'handoff_request.json').write_text(json.dumps(req,indent=2)+'\n')
ops=(A/'remote_ops.py').read_text().split("if __name__ == '__main__':")[0];body=activation.REMOTE_BODY.replace("directory/'direction_activation.json'","directory/'coverage_after_partial7_activation.json'")
audit=(PART/'guard_logic.py').read_text().split('def guard(req):')[0]
logic=(H/'guard_logic.py').read_text().replace('coverage_pilots','coverage_after_partial7').replace('coverage_partial_prerequisites_verified','coverage_after_partial7_prerequisites_verified').replace('waiting_partial_ten','waiting_retained_partial').replace("'total':10","'total':len(req['prerequisite_ids'])")
script=ops+'\n'+(H/'lifecycle.py').read_text()+'\n'+body+'\n'+audit+'\n'+logic+'\nREQ=json.loads('+repr(json.dumps(req))+')\n'
script+='''if __name__=='__main__':
 try:guard(REQ)
 except BlockingIOError:print('Existing coverage partial7 guard holds lock')
 except Exception as error:
  atomic(Path(REQ['root'])/'innovation_handoff/coverage_after_partial7_status.json',{'status':'failed','error':repr(error),'unix':time.time()});raise
'''
(P/'coverage_after_partial7_handoff.py').write_text(script);print('43 retained + 2 coverage; 7 partial prerequisites; 3 cancelled excluded')
