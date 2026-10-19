"""Hard lifetime and controller-loss guard; never touches an unregistered PID."""
import json,time
import service
from r31_contract import read
if __name__=='__main__':
    record=read(service.RUN/'processes/service.json')
    deadline=time.monotonic()+read(service.RUN/'configs/scientific_contract.json')['continuous']['max_service_seconds']
    grace=time.monotonic()+900
    while time.monotonic()<deadline:
        actual=service.current_identity(record['pid'])
        if actual is None or actual!=record['identity']:break
        controller=service.RUN/'processes/controller.json'
        if time.monotonic()>grace:
            if not controller.exists():break
            c=read(controller)
            if service.current_identity(c['pid'])!=c['identity']:break
        time.sleep(20)
    actual=service.current_identity(record['pid'])
    if actual==record['identity']:
        current=read(service.RUN/'processes/service.json')
        if current['pid']==record['pid'] and current['identity']==record['identity']:
            service.assert_owned(record);service.stop(expected_record=record)
