#include "audio_player.h"

 AUDIO_PLAYER::~AUDIO_PLAYER() {
    for (uint8_t i = 0; i < 128; ++i)
        held_notes[i] = 0;

 }

 AUDIO_PLAYER::~AUDIO_PLAYER() {
    delete stretcher;
    if(ringbuffer_a)
        jack_ringbuffer_free(ringbuffer_a);
    if(ringbuffer_b)
        jack_ringbuffer_free(ringbuffer_b);
}
