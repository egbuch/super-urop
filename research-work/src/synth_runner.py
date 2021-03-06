######
#
# Music system playback is possible thanks to:
#   Widget-based Synthesizer Logic thanks to Eran Egozy
#   Music21 Python Module via Michael Scott Cuthbert
#
######

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
import av_grid
import concurrent.futures as fut
import time

STRING_PATCH = 48
BRASS_PATCH = 61

## CC CHANNELS ##
VIBRATO_CC = 1
VOLUME_CC = 7
PAN_CC = 10
EXPRESSION_CC = 11
SUSTAIN_CC = 64
REVERB_CC = 91
CHORUS_CC = 93

class MainWidget(BaseWidget) :
    def __init__(self):
        super(MainWidget, self).__init__()

        self.audio = Audio(2) # set up audio
        self.song_path = '../scores/mario-song.musicxml' # set song path

        # create TempoMap, AudioScheduler
        self.tempo = 120 #TODO: grab tempo from file
        self.tempo_map  = SimpleTempoMap(self.tempo)
        self.sched = AudioScheduler(self.tempo_map)

        # Add a looper
        self.looper = looper.SongLooper(self.song_path, self.tempo)
        self.looper.initialize()

        # Set up FluidSynth
        self.synth = Synth('./synth_data/FluidR3_GM.sf2')
        self.note_velocity = 127

        # set up a midi channel for each part
        for i in range(len(self.looper.parts)):

            base_channel = 2*i
            switch_channel = 2*i + 1

            self.synth.program(base_channel, 0, 0)
            self.synth.program(switch_channel, 0, 0)

            # set the reverb
            self.synth.cc(base_channel, REVERB_CC, 127)
            self.synth.cc(switch_channel, REVERB_CC, 127)

            # set the EXPRESSION_CC
            self.synth.cc(base_channel, EXPRESSION_CC, 100)
            self.synth.cc(base_channel, EXPRESSION_CC, 100)

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

        self.current_rhythm = 'ORIGINAL'

        # concurrent processing of transformations
        self.executor = fut.ThreadPoolExecutor(max_workers=4)

    def on_cmd(self,tick, pitch, channel, velocity):
        self.synth.noteon(channel, pitch, velocity)

    def off_cmd(self,tick, pitch, channel):
        self.synth.noteoff(channel, pitch)

    def measure_update(self, now_beat, now_tick):
        # next step in the loop
        self.looper.step(now_beat + 1)

        # schedule each element that appears within the measure
        for i in range(len(self.looper.current_measure_in_parts)):
            part = self.looper.current_measure_in_parts[i]
            for j in range(len(part)):

                #retrieve the specific element in the measure
                element = part[j]
                dur = element.element.duration.quarterLength

                # ge millisecond timestamps that the element will be scheduled on
                on_tick = now_tick + (element.beatOffset + 1)*kTicksPerQuarter
                off_tick = on_tick + kTicksPerQuarter*dur

                # if the element is a note
                if element.is_note():
                    pitch = element.element.pitch.midi

                    # schedule note on and off
                    self.sched.post_at_tick(on_tick, self.on_cmd, pitch, 2*i, self.note_velocity)
                    self.sched.post_at_tick(off_tick, self.off_cmd, pitch, 2*i)

                    # switch channel should mirror silently
                    self.sched.post_at_tick(on_tick, self.on_cmd, pitch, 2*i + 1, self.note_velocity)
                    self.sched.post_at_tick(off_tick, self.off_cmd, pitch, 2*i + 1)

                # else if the element is a chord
                elif element.is_chord():
                    pitches = [pitch.midi for pitch in list(element.element.pitches)]

                    # schedule off and on events for each pitch in the chord
                    for pitch in pitches:
                        self.sched.post_at_tick(on_tick, self.on_cmd, pitch, 2*i, self.note_velocity)
                        self.sched.post_at_tick(off_tick, self.off_cmd, pitch, 2*i)

                        # swtich channel should mirror silently
                        self.sched.post_at_tick(on_tick, self.on_cmd, pitch, 2*i + 1, self.note_velocity)
                        self.sched.post_at_tick(off_tick, self.off_cmd, pitch, 2*i + 1)

    def on_update(self):
        self.audio.on_update()

        # current time
        now_beat = self.sched.get_current_beat()
        now_tick = self.sched.get_tick()

        #time of last measure
        previous_beat = self.looper.get_last_measure_beat()

        # take the difference, and see if it falls within the buffer-zone
        diff = now_beat - previous_beat
        mb = 3

        if (diff >= mb):
            # self.executor.submit(self.measure_update, now_beat, now_tick)
            self.measure_update(now_beat, now_tick)

        self.label.text = "Synthesizer and accompanying code via Eran Egozy (21M.385)" + '\n\n'
        self.label.text += self.sched.now_str() + '\n'
        self.label.text += 'key = ' + self.note_letter + self.accidental_letter + ' ' + self.mode + '\n'
        self.label.text += 'tempo = ' + str(self.tempo) + '\n'

class TransformationWidget(MainWidget):
    def __init__(self):
        super(TransformationWidget, self).__init__()

        # volume/dynamic control
        self.default_volume = 88
        self.volume_delta = 4
        self.current_volume = self.default_volume

        # tempo control
        self.tempo_delta = 8.0

        # keep track of key and rhythms
        self.key_changing = False
        self.rhythm_changing = False

        self.checking_transformation_done = False

        self.last_key_change_beat = 0

    #### TEMPO ###
    def tempoChanged(self):
        cur_time = self.tempo_map.tick_to_time(self.sched.get_tick())
        self.tempo_map.set_tempo(self.tempo, cur_time)
        self.looper.set_tempo(self.tempo)

    def tempoUp(self):
        self.tempo += 8
        self.tempoChanged()

    def tempoDown(self):
        self.tempo -= 8
        self.tempoChanged()

    def setTempo(self, tempo):
        self.tempo = tempo
        self.tempoChanged()

    #### Key and Mode ####
    def keyChanged(self, rhythm = None):
        new_key = self.note_letter + self.accidental_letter + ' ' + self.mode
        if new_key != self.looper.current_key:
            # # submit the actual transformation task to the executor
            self.executor.submit(self.looper.transform, None, new_key, rhythm)

    def rhythmChanged(self):
        # submit the actual transformation task to the executor
        self.executor.submit(self.looper.transform, None, None, self.current_rhythm)

    def checkKeyChange(self, note, accidental, mode):
        # if this results in a key change, then calculate the new transformation
        same_note = (self.note_letter == note)
        same_accidental = (self.accidental_letter == accidental)
        same_mode = (self.mode == mode)

        if not (same_note and same_accidental and same_mode):
            # if (self.last_key_change_beat == 0) or (self.sched.get_current_beat() - self.last_key_change_beat > 20) or not same_mode:
            if not same_mode:
                self.note_letter = note
                self.accidental_letter = accidental
                self.mode = mode

                self.key_changing = True
                self.last_key_change_beat = self.sched.get_current_beat()

    def checkRhythmChange(self, rhythm):
        if self.current_rhythm != rhythm:
            self.current_rhythm = rhythm
            self.rhythm_changing = True

    ### Instrument ###
    def switchInstruments(self, patches):
        # if not enough instruments from this point, fill with string and brass
        count = 0
        while len(patches) < len(self.looper.parts):
            if count % 2 == 0:
                patches.append(STRING_PATCH)
            else:
                patches.append(BRASS_PATCH)

            count += 1

        # apply instrument patches to synth base channels, and play switch channels louder
        for i in range(len(self.looper.parts)):

            # switch instruments base channels and make them quiet
            self.synth.program(2*i, 0, patches[i])
            self.setChannelVolume(2*i, 0)

            # play sound from switch CHANNELS
            self.setChannelVolume(2*i + 1, self.current_volume)

        # create the *linear* volume arc (list of values to iteratively set channels to for crescendo/decrescendo effect)
        volume_arc = list(range(0, self.current_volume, 5)) + [self.current_volume]

        # travel over arc
        for val in volume_arc:
            for i in range(len(self.looper.parts)):
                self.setChannelVolume(2*i, val)
                self.setChannelVolume(2*i + 1, self.current_volume - val)

            time.sleep(0.10)

        # finally, switch instruments in the switch channels to current instruments_multi
        for i in range(len(self.looper.parts)):
            # switch instruments base channels and make them quiet
            self.synth.program(2*i + 1, 0, patches[i])


    def setVolume(self):
        for i in range(len(self.looper.parts)):
            self.synth.cc(i, VOLUME_CC, self.current_volume)

    def setChannelVolume(self, i, value):
        self.synth.cc(i, VOLUME_CC, value)

    def on_update(self):
        if self.checking_transformation_done:
            if self.key_changing and not self.rhythm_changing:
                self.keyChanged()
                self.key_changing = False
            elif self.rhythm_changing and not self.key_changing:
                self.rhythmChanged()
                self.rhythm_changing = False
            elif self.key_changing and self.rhythm_changing:
                self.keyChanged(self.current_rhythm)
                self.key_changing = False
                self.rhythm_changing = False

            self.checking_transformation_done = False

        super(TransformationWidget, self).on_update()

class KeyboardWidget(TransformationWidget):
    """
    Control the music transformer via various keyboard inputs.
    """
    def __init__(self):
        super(KeyboardWidget, self).__init__()

        # Rhythm editting mechanism
        self.held_r = False # Keep track of whether R is being held down
        self.r_log = [] # Log of all numbers pressed
        self.rhythm = [] # Rhythm recorded

        # instrument edditing mechanism
        self.held_s = False
        self.s_log = []

        #parts control
        self.num_parts = len(self.looper.parts)
        self.current_part_index = 0

    def on_key_down(self, keycode, modifiers):

        note = self.note_letter
        accidental = self.accidental_letter
        mode = self.mode

        if keycode[1] in 'abcdefg':
            note = keycode[1]
        elif keycode[1] in '123456789':
            if self.held_r:
                self.r_log.append(int(keycode[1]))
            elif self.held_s:
                self.s_log.append(keycode[1])

        elif keycode[1] == 'r':
            self.held_r = True
            self.r_log = []

        elif keycode[1] == 's':
            self.held_s = True
            self.s_log = []

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
        elif keycode[1] == 'right':
            self.tempoUp()
        elif keycode[1] == 'left':
            self.tempo -= 8
            self.tempoChanged()
        elif keycode[1] == 'up':
            self.current_part_index = (self.current_part_index + 1) % self.num_parts
            self.r_log = []
            self.rhythm = []
        elif keycode[1] == 'down':
            self.current_part_index = (self.current_part_index - 1) % self.num_parts
            self.r_log = []
            self.rhythm = []

        self.checkKeyChange(note, accidental, mode)

    def on_key_up(self, keycode):
        if keycode[1] == 'r':
            self.held_r = False
            if len(self.r_log) >= 4:
                self.rhythm = self.r_log[-4:]
                self.executor.submit(self.looper.transform, [self.current_part_index], None, self.rhythm)
        elif keycode[1] == 's':
            self.held_s = False
            if len(self.s_log) == 1:
                self.synth.program(self.current_part_index, 0, int(self.s_log[0]))
            elif len(self.s_log) >= 2:
                self.synth.program(self.current_part_index, 0, int("".join(self.s_log[-2:])))

    def on_update(self):
        self.label.text += 'rhythm = ' + str(self.r_log[-4:]) + '\n'
        self.label.text += 'patch = ' + "".join(self.s_log[-2:]) + '\n'
        self.label.text += 'selected part = ' + str(self.current_part_index + 1) + '\n'
        super(KeyboardWidget, self).on_update()

class ArousalValenceWidget(TransformationWidget):
    """
    Control the music transformer via tuples of Arousal and Valence values that correspond
    to different values of musical attributes (Rhythm, Tempo, Instrument, etc).
    """
    def __init__(self):
        super(ArousalValenceWidget, self).__init__()

        self.arousal = 0
        self.valence = 0
        self.file = open('./data/av.txt', 'r')

        self.tempo_grid = av_grid.TempoGrid()
        self.tempo_grid.parse_point_file('./av-grid-points/tempo-mario.txt')

        self.rhythm_grid = av_grid.RhythmGrid()
        self.rhythm_grid.parse_point_file('./av-grid-points/rhythm-mario.txt')

        self.instrument_grid = av_grid.InstrumentGrid()
        self.instrument_grid.parse_point_file('./av-grid-points/instruments_multi-mario.txt')

        self.key_grid = av_grid.KeySignatureGrid()
        self.key_grid.parse_point_file('./av-grid-points/key-mario.txt')

    def transform_arousal_valence(self, arousal, valence):

        self.checking_transformation_done = False

        # print(arousal)
        # print(valence)

        try:
            self.change_note_velocity(arousal)
        except Exception as e:
            pass

        try:
            # tempo
            tempo_point, _ = self.tempo_grid.sample_parameter_point(arousal, valence)
            self.setTempo(tempo_point.get_value())
        except Exception as e:
            pass


        try:
            # rhythm
            rhythm_point, _ = self.rhythm_grid.sample_parameter_point(arousal, valence)
            self.checkRhythmChange(list(rhythm_point.get_value()))
        except Exception as e:
            pass

        try:
            # instrument
            instrument_point, _ = self.instrument_grid.sample_parameter_point(arousal, valence)
            self.executor.submit(self.switchInstruments, list(instrument_point.get_value()))
        except Exception as e:
            print("couldn't switch instruments")

        try:
            # key
            key_point, _ = self.key_grid.sample_parameter_point(arousal, valence)
            key_tuple = key_point.get_value()
            self.checkKeyChange(key_tuple[0], key_tuple[1], key_tuple[2])
        except Exception as e:
            pass

        self.checking_transformation_done = True

    def change_note_velocity(self, arousal):
        max_velocity = 127

        arousal += 1.0
        arousal /= 2.0

        velocity = max_velocity * arousal
        self.note_velocity = max(45, int(velocity))


    def on_update(self):
        where = self.file.tell()
        line = self.file.readline()
        if not line:
            self.file.seek(where)
        else:

            values = line.split(' ')
            self.arousal = float(values[0])
            self.valence = float(values[1])
            self.executor.submit(self.transform_arousal_valence, self.arousal, self.valence)

        super(ArousalValenceWidget, self).on_update()




run(eval('ArousalValenceWidget'))
