def add(a, b):
    return a + b

def divide(a, b):
    return a / b

def classify_number(value):
    if value > 0:
        if value % 2 == 0:
            return "positive-even"
        return "positive-odd"
    if value < 0:
        return "negative"
    return "zero"
