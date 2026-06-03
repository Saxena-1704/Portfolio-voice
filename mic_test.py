from microphone import Microphone

def callback(audio):
    print(len(audio))

mic = Microphone()

mic.start(callback)

input("Press Enter to stop...")

mic.stop()