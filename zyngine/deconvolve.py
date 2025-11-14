#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# This program has been "stolen" from:
# https://github.com/tamlablinz/Multichannel-IR-with-Jupyter
# and modified, removing some unneded fragments and adapted
# to work with zynthian multi-track recorded wav files.
# -----------------------------------------------------------------------------
# To work it requires:
#
# numpy
# scipy
# wavio
# -----------------------------------------------------------------------------

import wavio
import warnings
import numpy as np
from scipy import signal
from scipy.io import wavfile

warnings.filterwarnings('ignore')


def padarray(A, length, before=0):
    t = length - len(A) - before
    if t > 0:
        width = (before, t) if A.ndim == 1 else ([before, t], [0, 0])
        return np.pad(A, pad_width=width, mode='constant')
    else:
        width = (before, 0) if A.ndim == 1 else ([before, 0], [0, 0])
        return np.pad(A[:length - before], pad_width=width, mode='constant')


def ratio(dB):
    return np.power(10, dB * 1.0 / 20)


def filter20_20k(x, sr):
    '''
    filters everything outside of 20 - 20_000 Hz
    '''
    
    nyq = 0.5 * sr
    sos = signal.butter(5, [20.0 / nyq, 20_000.0 / nyq], btype='band', output='sos')
    return signal.sosfilt(sos, x)


def deconvolve(a, b, sr):  # per audio channel
    '''
    a is the input sweep signal, h the impulse response, and b the microphone-recorded signal. 
    We have a * h = b (convolution here!). 
    Let's take the discrete Fourier transform, we have fft(a) * fft(h) = fft(b), 
    then h = ifft(fft(b) / fft(a)).
    '''
    
    a = padarray(a, sr*50, before=sr*10)
    b = padarray(b, sr*50, before=sr*10)
    h = np.zeros_like(b)

    b1 = filter20_20k(b, sr)

    ffta = np.fft.rfft(a)
    fftb = np.fft.rfft(b1)
    ffth = fftb / ffta
    
    h1 = np.fft.irfft(ffth)
    h1 = filter20_20k(h1, sr)

    h = h1[:10 * sr]
    return h


class WavFromFile:
    def __init__(self, filename):
        self.nch = 1
        self.samplerate = 0
        self.data = None
        self.load(filename)

    def load(self, filename):
        self.samplerate, data = wavfile.read(filename)

        # Normalize input to 32bit float
        if data.dtype == np.int8:
            data = np.float32(data / (2**(24-1)))
        elif data.dtype == np.int16:
            data = np.float32(data / (2**(16-1)))
        elif data.dtype == np.int32:
            data = np.float32(data / (2**(32-1)))

        if data.ndim > 1:
            self.nch = data.shape[1]
        ch_data = np.empty((self.nch, data.shape[0]), dtype=np.float32)

        if self.nch > 1:
            for ch in range(self.nch):
                ch_data[ch] = data[:, ch]
        else:
            ch_data[0] = data
        self.data = ch_data


def writewav(filename, ch_data, samplerate, bitdepth):
    wavdata = np.column_stack([data for data in ch_data])
    wavio.write(filename, wavdata, samplerate, sampwidth=bitdepth//8)
    print(f'File "{filename}" written ({len(ch_data)} channels, {bitdepth}bit, {samplerate}Hz samplerate)')


def array_bounds(data, threshold):
    start = end = 0
    # Scan from start
    for i, value in enumerate(data):
        if abs(value) > threshold:
            start = i
            break
    # Scan from end
    for i, value in enumerate(data[::-1]):
        if abs(value) > threshold:
            end = len(data) - i
            break
    return start, end


def crop(ch_data, threshold):  # FIXME: not efficient
    start = ch_data[0].size
    end = 0
    return_data = []
    for data in ch_data:
        _start, _end = array_bounds(data, threshold)
        if _start < start:
            start = _start
        if _end > end:
            end = _end
    for data in ch_data:
        return_data.append(data[start:end])
    return np.array(return_data)


def limit(data, option=None):
    if option == 'clip':
        return np.clip(data, -1, 1)
    elif option == 'normalize':
        return data / max(data.max(), abs(data.min()))
    else:
        return data


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('recfile', help='filename with original sweep (channels 1 & 2) and recorded signal (channels 3-n)')
    parser.add_argument('outfile', help='filename for extracted impulse response (channels 3-n)')
    parser.add_argument('--limit', choices=['normalize', 'clip'], default='normalize', help='Normalize or clip resulting amplitudes')
    parser.add_argument('--crop', metavar='<threshold>', default=0, type=float, help='Crop resulting samples below threshold at start and end')
    parser.add_argument('--bitdepth', metavar='<bitdepth>', default=24, type=int, help='Set bit depth for outfile (defaults to 24)')
    parser.add_argument('--amp', metavar='<amplification>', default=0, type=float, help='Amplify resulting impulse response by given dB value')
    args = parser.parse_args()

    recording = WavFromFile(args.recfile)
    print(f"Loaded recording file: {len(recording.data)} channels")

    # Take sweep and recorded signal from a single multi-channel audio file, as generated by zynthian.
    sweep_data = recording.data[0]
    recording_data = recording.data[2:]

    # Deconvolve recorded audio channels
    ir = []
    for rec in recording_data:
        ir_channel = deconvolve(sweep_data, rec, recording.samplerate)
        ir.append(ir_channel)

    # Limit and crop output IR file
    wave = limit(np.array(ir), args.limit)
    wave = crop(wave, args.crop)

    # Write resulting IR file
    print(wave.shape)
    writewav(args.outfile, wave*ratio(args.amp), recording.samplerate, args.bitdepth)
