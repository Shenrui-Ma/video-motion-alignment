"""R79 uses individually reviewed submissions; automatic queues are disabled."""
def run(*args,**kwargs):
    raise RuntimeError('R79 automatic queue disabled; root approves and submits each individual job')
if __name__=='__main__':run()
