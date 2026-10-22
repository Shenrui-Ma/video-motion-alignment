from pathlib import Path
import importlib.util
p=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("contacts",p.parent/"action_contact_candidates/prepare_contacts.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.ROOT=p;m.IDS=["long_0166","long_0122"]
m.main()
