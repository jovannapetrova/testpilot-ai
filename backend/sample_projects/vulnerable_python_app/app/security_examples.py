import os
import subprocess

PASSWORD = "admin123"
API_KEY = "sk-test-hardcoded-secret"

def unsafe_eval(user_input):
    return eval(user_input)

def unsafe_shell(name):
    return subprocess.check_output(f"echo {name}", shell=True)

def fake_login(username, password):
    query = "SELECT * FROM users WHERE username='%s' AND password='%s'" % (username, password)
    return query
