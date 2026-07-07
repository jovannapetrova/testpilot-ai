from app.calculator import add, divide, classify_number

def test_add():
    assert add(2, 3) == 5

def test_divide():
    assert divide(10, 2) == 5

def test_classify_zero():
    assert classify_number(0) == "zero"
