#!/usr/bin/env python3
"""music.py — synthesizes the dark documentary score bed (build/music.wav)."""
import json, math
import numpy as np
from scipy.io import wavfile

SR = 44100
T = json.load(open('build/timeline.json'))
total = T['total'] + 1.0
n = int(total * SR)
t = np.arange(n) / SR

rng = np.random.default_rng(7)

# --- dark drone -------------------------------------------------------------
drone = (0.50 * np.sin(2 * np.pi * 55.0 * t)
         + 0.34 * np.sin(2 * np.pi * 82.41 * t + 0.7)
         + 0.22 * np.sin(2 * np.pi * 110.1 * t + 1.9))
lfo = 0.55 + 0.45 * np.sin(2 * np.pi * 0.05 * t)
drone *= lfo

# --- low rumble (one-pole lowpassed noise) ----------------------------------
noise = rng.normal(0, 1, n)
rumble = np.zeros(n)
a = 0.004
for_block = 200000
for s in range(0, n, for_block):
    e = min(n, s + for_block)
    for i in range(s, e):
        rumble[i] = rumble[i - 1] * (1 - a) + noise[i] * a if i else noise[i] * a
rumble *= 6.0

# --- heartbeat --------------------------------------------------------------
heart = np.zeros(n)
beat_iv = {0: 1.6, 1: 1.5, 2: 1.3, 3: 1.4, 4: 1.2, 5: 1.1}
for s_i, s in enumerate(T['segs']):
    iv = beat_iv[s_i]
    bt = s['start']
    while bt < s['start'] + s['dur']:
        i0 = int(bt * SR)
        if i0 < n:
            seg_len = int(0.45 * SR)
            seg_t = np.arange(min(seg_len, n - i0)) / SR
            thump = np.sin(2 * np.pi * 46 * seg_t) * np.exp(-7 * seg_t)
            thump2 = np.sin(2 * np.pi * 40 * (seg_t - 0.22)) * np.exp(-8 * (seg_t - 0.22)) * (seg_t > 0.22)
            heart[i0:i0 + len(seg_t)] += (thump + 0.6 * thump2) * 0.5
        bt += iv

# --- event stings / booms / risers ------------------------------------------
events = np.zeros(n)
def add_at(tt0, kind):
    i0 = int(tt0 * SR)
    if i0 >= n or i0 < 0:
        return
    if kind == 'sting':
        L = int(1.1 * SR); st = np.arange(min(L, n - i0)) / SR
        w = (np.sin(2*np.pi*221*st) + 0.7*np.sin(2*np.pi*329*st+0.4)
             + 0.5*np.sin(2*np.pi*441*st+1.1) + 0.3*np.sin(2*np.pi*659*st))
        events[i0:i0+len(st)] += w * np.exp(-4.2*st) * 0.30
    elif kind == 'boom':
        L = int(1.3 * SR); st = np.arange(min(L, n - i0)) / SR
        f = 72 * np.exp(-2.2 * st) + 30
        ph = 2 * np.pi * np.cumsum(f) / SR
        events[i0:i0+len(st)] += np.sin(ph) * np.exp(-2.6*st) * 0.65
        nb = rng.normal(0, 1, len(st)) * np.exp(-14*st) * 0.3
        events[i0:i0+len(st)] += nb
    elif kind == 'riser':
        L = int(1.0 * SR); st = np.arange(min(L, n - i0)) / SR
        ramp = (st / st[-1]) ** 2
        nb = rng.normal(0, 1, len(st))
        d = np.diff(nb, prepend=0)  # crude highpass
        events[i0:i0+len(st)] += d * ramp * 0.22
for e in T['events']:
    add_at(e['t'], e['kind'])

# --- combine + duck under narration -----------------------------------------
music = 0.34 * drone + 0.30 * rumble + 0.55 * heart + events
env = np.zeros(n)
for s in T['segs']:
    i0, i1 = int(s['start'] * SR), int((s['start'] + s['dur']) * SR)
    env[i0:i1] = 1.0
# smooth env
k = int(0.25 * SR)
kernel = np.ones(k) / k
env = np.convolve(env, kernel, mode='same')
duck = 0.55 - 0.33 * env
music *= duck

# gentle fade in/out
music[:SR] *= np.linspace(0, 1, SR)
music[-SR:] *= np.linspace(1, 0, SR)

peak = np.max(np.abs(music))
music = music / peak * 0.85
stereo = np.stack([music, music], axis=1)
wavfile.write('build/music.wav', SR, (stereo * 32767).astype(np.int16))
print('music.wav written', round(total, 2), 's, peak-norm 0.85')
