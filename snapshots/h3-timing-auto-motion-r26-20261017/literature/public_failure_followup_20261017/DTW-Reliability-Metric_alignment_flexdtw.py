import numpy as np
from numba import jit

@jit(nopython=True)
def flexdtw(C, steps, weights, buffer):
    """
    FlexDTW implementation for DTW with flexible steps and cost normalization.
    
    Inputs
    C: pairwise cost matrix
    steps: a numpy matrix specifying the allowable transitions. It should be of
        dimension (L, 2), where each row specifies (row step, col step)
    weights: a array that specifies the multiplicative weights for each transition
        type. The length of this array must match the number of possible transitions.
    buffer: specifies the length of a buffer region (in frames) to avoid short degenerate alignment paths
        near the corners of the pairwise cost matrix.
    
    Outputs
    best_cost: the best average cost per manhattan block
    path: the estimated warping path, specified as a 2xN array
    debug: Debugging information for examining the average cost per manhattan block for each 
        of the candidate ending positions.
    D: cumulative cost matrix
    B: backtrace matrix
    P: matrix specifying the starting location of the alignment path
    """
    
    # initialize
    D = np.zeros(C.shape)
    B = np.zeros(C.shape, dtype=np.int8)
    P = np.zeros(C.shape, dtype=np.int32)
    D[0,:] = C[0,:]
    D[:,0] = C[:,0]
    
    for row in range(1,C.shape[0]):
        for col in range(1, C.shape[1]):
            mincost = np.inf
            minidx = -1
            bestrprev = -1
            bestcprev = -1
            for stepidx, step in enumerate(steps):
                (rstep, cstep) = step
                prevrow = row - rstep
                prevcol = col - cstep
                if prevrow >= 0 and prevcol >= 0:
                    
                    # calculate avg cost per manhattan block
                    pathcost = D[prevrow, prevcol] + C[row, col] * weights[stepidx]
                    if P[prevrow, prevcol] >= 0:
                        mdist = row + (col - P[prevrow, prevcol])
                    else:
                        mdist = (row + P[prevrow, prevcol]) + col
                    cost_per_mb = pathcost / mdist
                    
                    # select best transition based on avg cost per manhattan block
                    if cost_per_mb < mincost:
                        mincost = cost_per_mb
                        minidx = stepidx
                        bestrprev = prevrow
                        bestcprev = prevcol
                        
            D[row, col] = D[bestrprev, bestcprev] + C[row, col] * weights[minidx]
            B[row, col] = minidx + 3
            if bestrprev == 0:
                P[row, col] = bestcprev
            elif bestcprev == 0:
                P[row, col] = -1*bestrprev
            else:
                P[row, col] = P[bestrprev, bestcprev]
            
    #  backtrack
    best_cost, best_r, best_c, debug = find_best_endpoint(D, P, buffer)
    path = backtrace_flexdtw(D, B, steps, best_r, best_c)
    path.reverse()
    path = np.array(path, dtype=np.int32)
    
    return best_cost, path.T, debug, D, B, P

@jit(nopython=True)
def find_best_endpoint(D, P, buffer):
    """
    Determines the best location to begin backtracking from by comparing the average path cost
    per manhattan block.
    """
    # Initialize debug with a type hint for Numba
    debug = [(0, 0.0, 0, 0)] 
    debug.pop(0) # Empty it immediately, but the type is now locked in
    
    # Clamp buffer to ensure candidates exist
    buffer = min(buffer, D.shape[0] - 1, D.shape[1] - 1)
    if buffer < 1:
        buffer = 1
    
    # consider last row and column as candidates
    candidates = [(D.shape[0]-1,i) for i in range(buffer, D.shape[1])] + [(i, D.shape[1]-1) for i in range(buffer, D.shape[0]-1)][::-1]
    
    best_cost = np.inf
    best_r, best_c = -1, -1
    
    for i, (r,c) in enumerate(candidates):
                
        # get alignment start location
        if P[r,c] >= 0:
            rstart, cstart = 0, P[r,c]
        else:
            rstart, cstart = -P[r,c], 0
            
        # calculate average cost per manhattan block
        mdist = (r - rstart) + (c - cstart) # manhattan distance
        avg_cost_per_mb = D[r,c] / mdist
        
        # keep best
        if avg_cost_per_mb < best_cost:
            best_cost = avg_cost_per_mb
            best_r, best_c = r, c
            
        # debugging info
        if r == D.shape[0]-1:
            debug.append((c-D.shape[1]+1, avg_cost_per_mb, r, c))
        else:
            debug.append((D.shape[0]-1-r, avg_cost_per_mb, r, c))
    
    # If no candidates (shouldn't happen now), fallback to bottom-right
    if best_r == -1:
        best_r, best_c = D.shape[0] - 1, D.shape[1] - 1
        mdist = best_r + best_c
        best_cost = D[best_r, best_c] / mdist
    
    return best_cost, best_r, best_c, debug

@jit(nopython=True)
def backtrace_flexdtw(D, B, steps, rstart, cstart):
    """
    Backtraces through the cumulative cost matrix D starting from a specified location.
    """
    pos = (rstart, cstart)
    path = []
    path.append(pos)
    while(pos[0] != 0 and pos[1] != 0):
        (row, col) = pos
        stepidx = B[row, col] - 3
        (rstep, cstep) = steps[stepidx]
        pos = (row-rstep, col-cstep)
        path.append(pos)
    
    return path
