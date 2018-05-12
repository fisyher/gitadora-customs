import cython
import numpy as np

STEPS = [
      256,  272,  304,   336,   368,   400,   448,   496,   544,   592,   656,   720,
      800,  880,  960,  1056,  1168,  1280,  1408,  1552,  1712,  1888,  2080,  2288,
     2512, 2768, 3040,  3344,  3680,  4048,  4464,  4912,  5392,  5936,  6528,  7184,
     7904, 8704, 9568, 10528, 11584, 12736, 14016, 15408, 16960, 18656, 20512, 22576,
     24832
]

CHANGES = [
    -1, -1, -1, -1, 2, 4, 6, 8,
    -1, -1, -1, -1, 2, 4, 6, 8
]

cdef class AdpcmWave:
    @cython.cdivision(True)
    def process_sample_batch(self, samples, samples_len, output, output_offset=0, output_sample_width=2, encode=False):
        cdef int step_index = 0
        cdef int pcm_sample = 0
        cdef int delta = 0
        cdef int sample = 0
        cdef int new_sample = 0
        cdef int sample_encode = 0
        cdef int v = 0
        cdef int step = 0
        cdef int change = 0
        cdef int mask = 0xfffffffe
        cdef int idx = 0

        while idx < samples_len:
            sample = samples[idx]

            step = STEPS[step_index]

            if encode:
                delta = sample - pcm_sample

                sign = 0
                if delta < 0:
                    sign = 0x08
                    delta = -delta

                v = (delta << 2)
                v = v // step

                if v > 7:
                    v = 7

                sample = sign | v
                sample_encode = sample

            # new_sample = (step >> 3) \
            #             + ((step >> 2) & -(sample & 1)) \
            #             + ((step >> 1) & -((sample >> 1) & 1)) \
            #             + (step & -((sample >> 2) & 1))

            new_sample = (step >> 3)
            if sample & 0x01:
                new_sample += (step >> 2) & mask
            if sample & 0x02:
                new_sample += (step >> 1) & mask
            if sample & 0x04:
                new_sample += step & mask

            change = CHANGES[sample % 16]
            step_index += change

            if step_index > 48:
                step_index = 48
            elif step_index < 0:
                step_index = 0

            if sample & 0x08:
                new_sample = -new_sample

            pcm_sample += new_sample

            if pcm_sample > 32767:
                pcm_sample = 32767
            elif pcm_sample < -32768:
                pcm_sample = -32768

            if encode:
                output[idx * output_sample_width][output_offset] = sample_encode
            else:
                output[idx * output_sample_width][output_offset] = pcm_sample

            idx += 1

        return output


    @staticmethod
    def decode_data(data, rate, channels, bits):
        decoders = [AdpcmWave()]

        if channels == 1:
            output = np.zeros((len(data) * 2, channels), dtype=np.int16)
            samples = np.zeros(len(data) * 2, dtype=np.int8)

            idx = 0
            for i in range(len(data)):
                samples[idx] = (data[i] >> 4) & 0x0f
                samples[idx + 1] = data[i] & 0x0f
                idx += 2

            output = decoders[0].process_sample_batch(samples, len(data) * 2, output, 0, 1)
        else:
            output = np.zeros((len(data), channels), dtype=np.int16)
            decoders.append(AdpcmWave())

            samples = np.zeros(len(data), dtype=np.int8)
            for i in range(len(data)):
                samples[i] = (data[i] >> 4) & 0x0f

            decoders[0].process_sample_batch(samples, len(data), output, 0, 1)

            for i in range(len(data)):
                samples[i] = data[i] & 0x0f

            decoders[1].process_sample_batch(samples, len(data), output, 1, 1)

        return output

    @staticmethod
    def encode_data(data, channels):
        output = np.zeros((len(data), 2), dtype=np.int8)
        encoders = [AdpcmWave()]

        if channels == 1:
            encoders[0].process_sample_batch(data, len(data), output, 0, 1, True)
        else:
            encoders.append(AdpcmWave())

            samples = np.zeros(len(data), dtype=np.int16)
            for i in range(len(data)):
                samples[i] = data[i][0]

            encoders[0].process_sample_batch(samples, len(data), output, 0, 1, True)

            for i in range(len(data)):
                samples[i] = data[i][1]

            encoders[1].process_sample_batch(samples, len(data), output, 1, 1, True)

        idx = 0
        output2 = np.zeros(len(data), dtype=np.int8)
        for i in range(0, len(output)):
            output2[idx] = ((output[i][0] << 4) | output[i][1]) & 0xff
            idx += 1

        return output2.tobytes()
