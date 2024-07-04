# demark.py
import pandas as pd

def demark_setup(data):
    data['Setup'] = 0
    for i in range(4, len(data)):
        if data['Close'].iloc[i] < data['Close'].iloc[i - 4]:
            data['Setup'].iloc[i] = data['Setup'].iloc[i - 1] + 1 if data['Setup'].iloc[i - 1] > 0 else 1
        elif data['Close'].iloc[i] > data['Close'].iloc[i - 4]:
            data['Setup'].iloc[i] = data['Setup'].iloc[i - 1] - 1 if data['Setup'].iloc[i - 1] < 0 else -1
    return data

def demark_countdown(data):
    data['Countdown'] = 0
    for i in range(2, len(data)):
        if data['Setup'].iloc[i] > 0 and data['Close'].iloc[i] <= data['Low'].iloc[i - 2]:
            data['Countdown'].iloc[i] = data['Countdown'].iloc[i - 1] + 1 if data['Countdown'].iloc[i - 1] > 0 else 1
        elif data['Setup'].iloc[i] < 0 and data['Close'].iloc[i] >= data['High'].iloc[i - 2]:
            data['Countdown'].iloc[i] = data['Countdown'].iloc[i - 1] - 1 if data['Countdown'].iloc[i - 1] < 0 else -1
    return data