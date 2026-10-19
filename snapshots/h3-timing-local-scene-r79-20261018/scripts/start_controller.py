"""R79 deliberately has no automatic controller."""
def main():
    raise RuntimeError('R79 automatic controller disabled; use service-only and individually approved job.submit')
if __name__=='__main__':main()
