# -*- coding: utf-8 -*-

import sys

PY3 = sys.version_info>(3,0)
PY2 = sys.version_info<(3,0)

if PY3:
    import queue as Queue
    input=input


elif PY2:
    import Queue
    input=raw_input



