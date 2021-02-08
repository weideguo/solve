# -*- coding: utf-8 -*-
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.playbook_parser import simple_parser


if __name__ == "__main__":

    playbook="playbook/simple/simple_demo.txt"
    cmd_generator = simple_parser(playbook)  
    
    for next_cmd in cmd_generator:
        print(next_cmd)

    """
    cmd_generator.next()
    cmd_generator.next()
    cmd_generator.next()
    """


