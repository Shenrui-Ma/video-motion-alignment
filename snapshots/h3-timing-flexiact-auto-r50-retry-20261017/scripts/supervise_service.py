"""Wait for the unchanged task service and persist its actual child exit status."""
import json
import os
import time

import service


def decode_wait_status(status):
    if os.WIFEXITED(status):
        return {"exit_code": os.WEXITSTATUS(status), "signal": None}
    if os.WIFSIGNALED(status):
        return {"exit_code": None, "signal": os.WTERMSIG(status),
                "core_dumped": bool(os.WCOREDUMP(status))}
    raise RuntimeError(f"Unexpected nonterminal wait status: {status}")


def main():
    pid = os.getpid()
    record = {"pid": pid, "identity": service.identity(pid),
              "started_unix": time.time(), "role": "service_exit_status_supervisor"}
    paths = [service.RUN / "processes/supervisor.json",
             service.RUN / f"processes/supervisor_{pid}.json"]
    for path in paths:
        service.write_json(path, record)
    try:
        # This function creates our direct child with its original command,
        # environment, admission check, separate session, and service lock.
        child = service.start(cache_none=False)
        record.update(service_pid=child["pid"], service_identity=child["identity"], service_record=child)
        for path in paths:
            service.write_json(path, record)
        waited_pid, status = os.waitpid(child["pid"], 0)
        result = {"supervisor": record, "service_pid": waited_pid,
                  "service_identity": child["identity"], "exited_unix": time.time(),
                  "raw_wait_status": status, **decode_wait_status(status)}
        service.write_json(service.RUN / f"processes/service_exit_{waited_pid}.json", result)
        service.write_json(service.RUN / f"processes/supervisor_exit_{pid}.json", result)
        print(json.dumps(result), flush=True)
    except BaseException as exc:
        service.write_json(service.RUN / f"processes/supervisor_error_{pid}.json",
                           {"supervisor": record, "observed_unix": time.time(),
                            "error": repr(exc)})
        raise


if __name__ == "__main__":
    main()
