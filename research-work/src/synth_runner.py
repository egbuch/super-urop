import sys
sys.path.append('..')
from common.core import *
from common.audio import *
from common.synth import *
from common.gfxutil import *
from common.clock import *
from common.metro import *
import music21 as m21
import analyzer
import transformer
import looper
import concurrent.futures as fut

#TODO A sequence of Rhythmic transformation that will increase tension
#TODO Start with 2D Emotion mapping between valence and arousal, such that you map numerical values to emotions, start mapping different musical concepts to arousal/valence
#TODO think about video game -> valence/arousal -> music transformation

#TODO supermario hard-coded demo
#TODO manipulating of the order of the measures, repeats, increase tension

class MainWidget(BaseWidget) :
    def __init__(self):
        super(MainWidget, self).__init__()

        self.audio = Audio(2)
        self.synth = Synth('./synth_data/FluidR3_GM.sf2')

        # Set up FluidSynth
        self.channel = 0 #TODO: look into m21 channel
        self.patch = (0, 0) #TODO: Get patch from m21
        self.synth.program(self.channel, self.patch[0], self.patch[1])

        self.song_path = '../scores/hogwarts-forever.xml'

        # create TempoMap, AudioScheduler
        self.tempo = 120 #TODO: grab tempo from file
        self.tempo_map  = SimpleTempoMap(self.tempo)
        self.sched = AudioScheduler(self.tempo_map)

        # Add a looper
        self.looper = looper.SongLooper(self.song_path, self.tempo)
        self.looper.initialize()

        # connect scheduler into audio system
        self.audio.set_generator(self.sched)
        self.sched.set_generator(self.synth)

        # and text to display our status
        self.label = topleft_label()
        self.add_widget(self.label)

        # as the loop continues, these values will be updated to the current transformation
        key_info = self.looper.initial_key.split(" ")
        self.note_letter = key_info[0][0]
        self.accidental_letter = key_info[0][1] if len(key_info[0]) == 2 else ''
        self.mode = key_info[1]

        # Rhythm editting mechanism
        self.held_r = False # Keep track of whether R is being held down
        self.r_log = [] # Log of all numbers pressed
        self.rhythm = [] # Rhythm recorded

        # concurrent processing of transformations
        self.executor = fut.ThreadPoolExecutor(max_workers=10)

    def on_cmd(self, tick, pitch):
        self.synth.noteon(self.channel, pitch, 100)

    def off_cmd(self, tick, pitch):
        self.synth.noteoff(self.channel, pitch)

    def on_key_down(self, keycode, modifiers):
        note = self.note_letter
        accidental = self.accidental_letter
        mode = self.mode
        if keycode[1] in 'abcdefg':
            note = keycode[1]
        elif keycode[1] in '123456789':
            if self.held_r:
                self.r_log.append(int(keycode[1]))

        elif keycode[1] == 'i':
            accidental = '#'
        elif keycode[1] == 'p':
            accidental = '-'
        elif keycode[1] == 'o':
            accidental = ''
        elif keycode[1] == '-':
            mode = 'major'
        elif keycode[1] == '=':
            mode = 'minor'
        elif keycode[1] == 'r':
            self.held_r = True
            self.r_log = []
        elif keycode[1] == 'right':
            self.tempo += 8
            cur_time = self.tempo_map.tick_to_time(self.sched.get_tick())
            self.tempo_map.set_tempo(self.tempo, cur_time)
            self.looper.set_tempo(self.tempo)
        elif keycode[1] == 'left':
            self.tempo -= 8
            cur_time = self.tempo_map.tick_to_time(self.sched.get_tick())
            self.tempo_map.set_tempo(self.tempo, cur_time)
            self.looper.set_tempo(self.tempo)

        current_tonic = self.note_letter + self.accidental_letter
        current_mode = self.mode

        new_tonic = note + accidental
        new_mode = mode

        new_key = new_tonic + " " + new_mode

        # if this results in a key change, then calculate the new transformation
        if current_tonic != new_tonic or current_mode != new_mode:
            self.executor.submit(self.looper.transform, None, new_key, None)

            self.note_letter = note
            self.accidental_letter = accidental
            self.mode = mode

    def on_key_up(self, keycode):
        if keycode[1] == 'r':
            self.held_r = False
            if len(self.r_log) >= 4:
                self.rhythm = self.r_log[-4:]
                self.executor.submit(self.looper.transform, None, None, self.rhythm)

    def on_update(self) :
        self.audio.on_update()

        # current time
        now_beat = self.sched.get_current_beat()
        now_tick = self.sched.get_tick()

        #time of last measure
        previous_beat = self.looper.get_last_measure_beat()

        # take the difference, and see if it falls within the buffer-zone
        diff = now_beat - previous_beat
        mb = 4

        if (diff == mb):
            print("hit")
            # next step in the loop
            self.looper.step(now_beat)

            # schedule each element that appears within the measure
            for part in self.looper.current_measure_in_parts:
                for i in range(len(part)):

                    #retrieve the specific element in the measure
                    element = part[i]
                    dur = element.element.duration.quarterLength
                    # ge millisecond timestamps that the element will be scheduled on
                    on_tick = now_tick + element.beatOffset*kTicksPerQuarter
                    off_tick = on_tick + kTicksPerQuarter*dur

                    # if the element is a note
                    if element.is_note():
                        pitch = element.element.pitch.midi

                        # schedule note on
                        self.sched.post_at_tick(on_tick, self.on_cmd, pitch)

                        # schedule note off
                        self.sched.post_at_tick(off_tick, self.off_cmd, pitch)

                    # else if the element is a chord
                    elif element.is_chord():
                        pitches = [pitch.midi for pitch in list(element.element.pitches)]

                        # schedule off and on events for each pitch in the chord
                        for pitch in pitches:
                            self.sched.post_at_tick(on_tick, self.on_cmd, pitch)
                            self.sched.post_at_tick(off_tick, self.off_cmd, pitch)


        self.label.text = self.sched.now_str() + '\n'
        self.label.text += 'key = ' + self.note_letter + self.accidental_letter + ' ' + self.mode + '\n'
        self.label.text += 'rhythm = ' + str(self.r_log[-4:]) + '\n'
        self.label.text += 'tempo = ' + str(self.tempo) + '\n'


run(eval('MainWidget'))
