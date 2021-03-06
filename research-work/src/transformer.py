import music21 as m21
import numpy as np
import sklearn as skl
import sys
from collections import defaultdict
from random import shuffle
import copy
import unittest
import random
import analyzer

# TODO: Test cases
# class TransformationTests(unittest.TestCase):
#     import


# transformation 1
def transpose_to_new_key(measures, key):
    """
    Translates all notes from their current key to the new key

    Args:
        measures (List[List[AnalyzedNotes]]): Song notes grouped by measure
        key (music21.key.Key): The key signature context.

    Returns:
        transposed_measures (List[List[AnalyzedNote]]): List of transposed notes grouped by their
                                                        corresponding measures.
    """
    transposed_measures = []
    for measure in measures:
        m = [note.in_new_key(key) for note in measure]

        transposed_measures.append(m)

    return transposed_measures

# transformation 2
def fill_ostinato(measures, rhythm):
    """
    Takes the rhythm and applies the rhythm over the
    measures in the song. Forms a song structured on a single
    rhythmic idea.

    Args:
        measures (List[List[AnalyzedNote]]) Analyzed notes grouped in measures
        rhythm (List[int]) List, whose length == 4, where each index specifies the quarter-note
                           division being played. Ex: 2 = eighth notes, 3 = eighth note triplets, etc.

    Returns:
        ostinated_measures(List[List[AnalyzedNote]]): list of measures with the repeated rhythm applied
    """
    assert(len(rhythm) == 4)

    # ostinato doesn't currently work on rests, so replace them with notes
    # measures = replace_rests(measures)

    ostinated_measures = []
    for measure in measures:

        # dictonary that maps the present elementss to the previous quarter-note beat
        # for example, if beat 2 of the measure has sixteenth notes, there will then 2 -> [N, N, N, N]
        prev_elements_on_beats = defaultdict(list)

        #return measure
        m = []

        # map each element to its previous strong beat
        for element in measure:
            if not element.is_rest():
                # previous quarter note beat number
                beat = int(element.beatOffset)

                # place the element to its prev beat.
                prev_elements_on_beats[beat].append(element)

        beat_to_element_keys = prev_elements_on_beats.keys()

        for i in range(len(rhythm)):
            # current quarter note beat == i + 1
            elements = []
            cur_index = i + 1

            if cur_index not in beat_to_element_keys:
                rest_element = m21.note.Rest()
                rest_element.duration =  m21.duration.Duration(quarterLength=1.0)

                analyzed_rest = analyzer.AnalyzedElement(m21.key.Key('c', 'major'), rest_element, beatOffset=cur_index)
                m.append(analyzed_rest)

            else:
                # find elements. if current index beat doesn't have note attacks, look at previous beats
                # this takes care of the case where the previous element has duration > quarter length (i.e. a half note),
                # such that the next beat has no attack (and thus no elements)
                while len(elements) == 0 and cur_index > 0:
                    if cur_index in beat_to_element_keys:
                        elements = prev_elements_on_beats[cur_index]
                    cur_index -= 1

                # 1 = quarter, 2 = eighth, 3 = eighth triplet, 4 = sixteenth notes, etc.
                num_elements_for_rhythm = rhythm[i]
                ql = 1.0/num_elements_for_rhythm

                # if there are equal notes as required for the new rhythm
                if num_elements_for_rhythm == len(elements):
                    for element in elements:
                        new_element = copy.deepcopy(element.element) # TODO: Deep copying can be slow
                        new_element.duration = m21.duration.Duration(quarterLength=ql)

                        m.append(element.copy(element=new_element))

                elif num_elements_for_rhythm > len(elements):
                    # divide the rhythm evenly along notes
                    times = [int(num_elements_for_rhythm/len(elements)) for n in range(len(elements))]

                    extra = num_elements_for_rhythm % len(elements)

                    # if not even, add extra notes from the beginning
                    if extra != 0:
                        for x in range(extra):
                            times[x] += 1

                    internal_offset = 0
                    for j in range(len(elements)):
                        element = elements[j]
                        t = times[j]

                        # t = some integer
                        for repeat in range(t):
                            offset = (i + 1) + (internal_offset)*ql

                            new_element = copy.deepcopy(element.element) #TODO Deep copy might be slow
                            new_element.duration = m21.duration.Duration(quarterLength=ql)

                            m.append(element.copy(element=new_element, beatOffset=offset))
                            internal_offset += 1

                else:
                    first = elements[::2]
                    then = elements[1::2]

                    seq = first + then
                    for j in range(num_elements_for_rhythm):
                        element = seq[j]

                        new_element = copy.deepcopy(element.element)
                        new_element.duration = m21.duration.Duration(quarterLength=ql)

                        offset = (i + 1) + j*ql
                        m.append(element.copy(element=new_element, beatOffset=offset))

        ostinated_measures.append(m)

    return ostinated_measures

# transformation 3
def replace_rests(measures):
    """
    Removes all rests from measures, and replaces them with a nearby note

    Args:
        measures (List[List[AnalyzedNote]]) Analyzed notes grouped in measures

    Returns:
        altered_measures(List[List[AnalyzedNote]]): list of measures with replaced rests.
    """
    altered_measures = []

    for measure in measures:
        m = []

        # find all non-rest notes in measure
        non_rest_elements = list(filter(lambda x: not x.is_rest(), measure))

        if len(non_rest_elements) == 0:
            if altered_measures:
                measure = altered_measures[-1]
                altered_measures.append(measure)
                continue
            else:
                continue

        for i in range(len(measure)):
            element = measure[i]

            if element.is_rest():
                replace_element = random.choice(non_rest_elements)
                new_element = copy.deepcopy(replace_element.element)
                m.append(element.copy(element=new_element))

            else:
                m.append(element)

        altered_measures.append(m)

    return altered_measures
