"""Physical headroom and allocator are independent; Comfy reserve is inside cap."""
def admit_before_context(free_mib,minimum_free_mib=22500):
 return free_mib>=minimum_free_mib

def admit_after_context(physical_free_bytes,allocator_reserved_bytes,allocator_cap_bytes,external_headroom_mib=1536):
 # Reserved memory belongs to this process and is already excluded from physical free.
 # Adding it once makes this valid both immediately after CUDA init and after tiny probes.
 return physical_free_bytes+allocator_reserved_bytes>=allocator_cap_bytes+external_headroom_mib*1024**2
