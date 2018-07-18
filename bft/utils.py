def max_corrupted_peers(n):
    # 3 -> 0
    # 4 -> 1
    # 5 -> 1
    # 6 -> 1
    # 7 -> 2
    return (n - 1) // 3
