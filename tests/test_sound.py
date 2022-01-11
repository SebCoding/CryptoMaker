import os
import time
import winsound

def beep(nb, frequency, duration):
    # frequency: Set Frequency To 2500 Hertz
    # duration: Set Duration To 1000 ms == 1 second
    if os.name == 'nt':
        import winsound

        for i in range(nb):
            winsound.Beep(frequency, duration)
            time.sleep(0.1)

# winsound.Beep(2000, 100)
#
# winsound.Beep(500, 500)

#beep(1, 500, 2000)

beep(3, 500, 1000)