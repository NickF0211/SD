Instruction for launching AutoCheck:

# AutoCheck
# This is the anonymous repo for tool AutoCheck

### prerequisite:
1. Python 3.5 and later


3. z3-solver with python binding:
    `pip install z3-solver` or 
    `pip3 install z3-solver`
    
4. pysmt:
    `pip install pysmt` or 
    `pip3 install pysmt`

5. `pip install ordered-set`

6. `pip install textx`
    

### Launch AutoCheck
`python3 sleecFrontEnd.py`

At this point, an UI window should have popped up.
Edit the text in the window to customize your SLEEC rules

### Examples
Example rules: dressingrobot.sleec,  dressingrobot-1.sleec
, dressingrobot-2.sleec, dressingrobot-3.sleec, Example3.sleec


Redudency checking and rule Checking are avaialble for all rules, and concern 
checking is available if concerns are given in the .sleec files. dressingrobot-3.sleec
contains an example of concern.
