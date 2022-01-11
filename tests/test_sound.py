import os
import time


def beep(nb, silence_time=0.1):
    if os.name == 'nt':
        import winsound
        frequency = 1500  # Set Frequency To 2500 Hertz
        duration = 500  # Set Duration To 1000 ms == 1 second
        for i in range(nb):
            winsound.Beep(frequency, duration)
            time.sleep(silence_time)

beep(5)