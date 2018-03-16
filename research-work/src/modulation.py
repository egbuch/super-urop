import music21 as m21
from collections import defaultdict
import random

PITCHES = ['A-', 'A', 'A#', 'B-', 'B', 'C', 'C#', 'D-', 'D', 'D#', 'E-', 'E', 'F', 'F#', 'G-', 'G', 'G#']

class KeyNode:
    def __init__(self, tonic, mode):
        self.tonic = tonic.lower()
        self.mode = mode.lower()
        self.edges = {} # commond chord edges

    def insert_edge(self, other_node, chords):
        if chords:
            self.edges[other_node] = chords
            other_node.edges[self] = chords

    def get_adjacent_vertices(self):
        return self.edges.keys()

    def is_connected(self, other):
        return (other in self.get_adjacent_vertices()) or (self in other.get_adjacent_vertices())

    def __eq__(self, other):
        return self.tonic == other.tonic and self.mode == other.mode

    def __hash__(self):
        return hash((self.tonic, self.mode))

class KeyModulator:
    def __init__(self):

        # triad dictionaries by key
        self.triads_by_major_key = {}
        self.triads_by_minor_key = {}

        # dominant/dminished chords by tonic
        self.dominant_7th_by_key = {}
        self.diminished_7th_by_key = {}

        # major tonic
        self.tonic_by_major_key = {}
        self.tonic_by_minor_key = {}

        # graph container
        self.common_chord_graph = []


        # MAJOR TRIADS PRE-PROCESSING
        for pitch in PITCHES:
            # generate scale and get pitches froms scale
            scale = m21.scale.MajorScale(pitch)
            scale_pitches = [str(p) for p in scale.getPitches()]
            scale_pitches = scale_pitches + scale_pitches[1:6]

            # create set of all triads in that scale
            triads = set()
            for p in range(len(scale_pitches) - 5):
                root = scale_pitches[p][:-1]
                third = scale_pitches[p + 2][:-1]
                fifth = scale_pitches[p + 4][:-1]

                if p != 2: # iii chord in Major key is never used
                    triads.add((root, third, fifth))

                if p == 0:
                    self.tonic_by_major_key[pitch] = (root, third, fifth)

                if p == 4:
                    seventh = scale_pitches[p + 6][:-1]
                    dom_seventh = (root, third, fifth, seventh)
                    self.dominant_7th_by_key[pitch] = dom_seventh

                if p == 6:
                    if scale_pitches[p + 6][-2] == "#":
                        seventh = scale_pitches[p + 6][:-2]
                    else:
                        seventh = scale_pitches[p + 6][:-1] + '-'
                    dim_seventh = (root, third, fifth, seventh)
                    self.diminished_7th_by_key[pitch] = dim_seventh


            self.triads_by_major_key[pitch] = triads

        # MINOR TRIADS PRE-PROCESSING
        for pitch in PITCHES:
            # generate scale and get pitches froms scale
            scale = m21.scale.MinorScale(pitch)
            scale_pitches = [str(p) for p in scale.getPitches()]
            scale_pitches = scale_pitches + scale_pitches[1:6]

            # create set of all triads in that scale
            triads = set()
            for p in range(len(scale_pitches) - 4):
                root = scale_pitches[p][:-1]
                third = scale_pitches[p + 2][:-1]
                fifth = scale_pitches[p + 4][:-1]
                triads.add((root, third, fifth))

                if p == 0:
                    self.tonic_by_minor_key[pitch] = (root, third, fifth)

            self.triads_by_minor_key[pitch] = triads

        for pitch1 in PITCHES:

            node_1_major = KeyNode(pitch1, 'major')
            node_1_minor = KeyNode(pitch1, 'minor')

            # get the current major node if it already exists
            if node_1_major in self.common_chord_graph:
                get_index = self.common_chord_graph.index(node_1_major)
                node_1_major = self.common_chord_graph[get_index]
            else:
                self.common_chord_graph.append(node_1_major)

            # get the current minor node if it already exists
            if node_1_minor in self.common_chord_graph:
                get_index = self.common_chord_graph.index(node_1_minor)
                node_1_minor = self.common_chord_graph[get_index]
            else:
                self.common_chord_graph.append(node_1_minor)

            # get the major and minor triads for this scale
            major_triads1 = self.triads_by_major_key[pitch1]
            minor_triads1 = self.triads_by_minor_key[pitch1]

            for pitch2 in PITCHES:

                node_2_major = KeyNode(pitch2, 'major')
                node_2_minor = KeyNode(pitch2, 'minor')

                # get the current major node if it already exists
                if node_2_major in self.common_chord_graph:
                    get_index = self.common_chord_graph.index(node_2_major)
                    node_2_major = self.common_chord_graph[get_index]
                else:
                    self.common_chord_graph.append(node_2_major)

                # get the current minor node if it already exists
                if node_2_minor in self.common_chord_graph:
                    get_index = self.common_chord_graph.index(node_2_minor)
                    node_2_minor = self.common_chord_graph[get_index]
                else:
                    self.common_chord_graph.append(node_2_major)

                major_triads2 = self.triads_by_major_key[pitch2]
                minor_triads2 = self.triads_by_minor_key[pitch2]

                if pitch1[0] != pitch2[0]:
                    # Major Key -> Major Key
                    if node_2_major not in node_1_major.get_adjacent_vertices():
                        major_major = list(major_triads1.intersection(major_triads2))
                        node_1_major.insert_edge(node_2_major, major_major)

                    # Minor Key -> Minor Key
                    if node_2_minor not in node_1_minor.get_adjacent_vertices():
                        minor_minor = list(minor_triads1.intersection(minor_triads2))
                        node_1_minor.insert_edge(node_2_minor, minor_minor)

                    # Major Key -> Minor Key
                    if node_2_minor not in node_1_major.get_adjacent_vertices():
                        major_minor = list(major_triads1.intersection(minor_triads2))
                        node_1_major.insert_edge(node_2_minor, major_minor)

                    # Minor Key -> Major Key
                    if node_2_major not in node_1_minor.get_adjacent_vertices():
                        minor_major = list(minor_triads1.intersection(major_triads2))
                        node_1_minor.insert_edge(node_2_major, minor_major)
                else:
                    # Parallel Major <-> Minor can use modal mixture (any chord in either key)
                    if node_2_minor not in node_1_major.get_adjacent_vertices():
                        major_minor = list(major_triads1.union(minor_triads2))
                        node_1_major.insert_edge(node_2_minor, major_minor)

                    if node_2_major not in node_1_minor.get_adjacent_vertices():
                        minor_major = list(minor_triads1.union(major_triads2))
                        node_1_minor.insert_edge(node_2_major, minor_major)


    def print_graph(self):
        for node in self.common_chord_graph:
            print (node.tonic + ' ' + node.mode)
            for k, v in node.edges.items():
                print (k.tonic + ' ' + k.mode, v)
            print("-----------------------------------")

    def add_cadence(self, key, mode, current_path):
        # I chord
        if mode.lower() == 'major':
            current_path.append(self.tonic_by_major_key[key.upper()])

            # I like the sound of either dominant or diminshed 7ths in major, so randomize
            k = random.randint(0, 1)
            if k == 0:
                current_path.append(self.dominant_7th_by_key[key.upper()])
            else:
                current_path.append(self.diminished_7th_by_key[key.upper()])
        else:
            # I prefer only diminished triads in minor
            current_path.append(self.tonic_by_minor_key[key.upper()])
            current_path.append(self.diminished_7th_by_key[key.upper()])

    def add_tonic(self, key, mode, current_path):
        if mode.lower() == 'major':
            current_path.append(self.tonic_by_major_key[key.upper()])
        else:
            current_path.append(self.tonic_by_minor_key[key.upper()])

    def find_chord_path(self, start_tuple, end_tuple):

        start_node = KeyNode(start_tuple[0].lower(), start_tuple[1].lower())
        index = self.common_chord_graph.index(start_node)
        start_node = self.common_chord_graph[index]

        levels = {}
        queue = []

        levels[start_node] = None
        for node in start_node.get_adjacent_vertices():
            queue.append(node)
            levels[node] = start_node

        goal_node = None
        while queue:
            current_node = queue.pop(0)
            if current_node.tonic == end_tuple[0].lower() and current_node.mode == end_tuple[1].lower():
                goal_node = current_node
                break
            else:
                for node in current_node.get_adjacent_vertices():
                    if node not in set(levels.keys()):
                        queue.append(node)
                        levels[node] = current_node

        if not goal_node:
            return None

        path = []
        # end the path  with 7th chord function -> tonic (path is reversed, so put it first)

        self.add_cadence(end_tuple[0], end_tuple[1], path)

        # get the chord progression path
        while goal_node:
            parent = levels[goal_node]
            if parent:
                pivot_chord = parent.edges[goal_node][0]

                # we're starting with the tonic, don't add a cadence to where we've started... (redundant)
                if levels[parent]:
                    self.add_cadence(parent.tonic, parent.mode, path)

                path.append(pivot_chord)

            # set up next iteration of while loop, up the ancestry tree
            goal_node = parent

        self.add_tonic(start_tuple[0], start_tuple[1], path)
        return path[::-1]


# mod = KeyModulator()
# path = mod.find_chord_path(('b-', 'Major'), ('a-', 'major'))
#
# path = [m21.chord.Chord(n) for n in path]
# print(path)
#
# stream = m21.stream.Stream()
# for n in path:
#     stream.append(n)
#
# stream.show('midi')

# TODO: Verify that there is an edge going from parallel major/minors
