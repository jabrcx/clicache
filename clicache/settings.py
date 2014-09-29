# Copyright (c) 2014, John A. Brunelle
# All rights reserved.

import os

# CLICACHE_DIR
# the root of the cache
# it's not required to exist beforehand (nor are its parents)
CLICACHE_DIR = os.environ.get('CLICACHE_DIR', '~/.clicache')

# CLICACHE_MAX_RETRIES
# The algorithms employed here are not perfect -- certain operations may be
# foiled by race conditions.  However, the algorithms detect when that's the
# case, and retry.  To avoid infinite loops due to other, unexpected failures,
# this is the maximum number of times an operations will be retried.
CLICACHE_MAX_RETRIES = os.environ.get('CLICACHE_MAX_RETRIES', 10)
