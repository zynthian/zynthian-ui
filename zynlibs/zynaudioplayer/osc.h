#include "tinyosc.h" //provides OSC interface

#define MAX_OSC_CLIENTS 5 // Maximum quantity of OSC clients
#define OSC_PORT 9000 // UDP/IP port for OSC communication

char g_oscbuffer[1024]; // Used to send OSC messages
char g_oscpath[32]; // OSC path
int g_oscfd = -1; // File descriptor for OSC socket
int g_bOsc = 0; // True if OSC client subscribed
struct sockaddr_in g_oscClient[MAX_OSC_CLIENTS]; // Array of registered OSC clients
pthread_t g_osc_thread; // ID of OSC listener thread
uint8_t g_run_osc = 1; // 1 to keep OSC listening thread running

void sendOscFloat(const char* path, float value) {
    if(g_oscfd == -1)
        return;
    int len = tosc_writeMessage(g_oscbuffer, sizeof(g_oscbuffer), path, "f", value);
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if(g_oscClient[i].sin_addr.s_addr == 0)
            continue;
        sendto(g_oscfd, g_oscbuffer, len, MSG_CONFIRM|MSG_DONTWAIT, (const struct sockaddr *) &g_oscClient[i], sizeof(g_oscClient[i]));
    }
}

void sendOscInt(const char* path, int value) {
    if(g_oscfd == -1)
        return;
    int len = tosc_writeMessage(g_oscbuffer, sizeof(g_oscbuffer), path, "i", value);
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if(g_oscClient[i].sin_addr.s_addr == 0)
            continue;
        sendto(g_oscfd, g_oscbuffer, len, MSG_CONFIRM|MSG_DONTWAIT, (const struct sockaddr *) &g_oscClient[i], sizeof(g_oscClient[i]));
    }
}

void sendOscString(const char* path, const char* value) {
    if(g_oscfd == -1)
        return;
    if(strlen(value) >= sizeof(g_oscbuffer))
        return;
    int len = tosc_writeMessage(g_oscbuffer, sizeof(g_oscbuffer), path, "s", value);
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if(g_oscClient[i].sin_addr.s_addr == 0)
            continue;
        sendto(g_oscfd, g_oscbuffer, len, MSG_CONFIRM|MSG_DONTWAIT, (const struct sockaddr *) &g_oscClient[i], sizeof(g_oscClient[i]));
    }
}

int _addOscClient(const char* client) {
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if(g_oscClient[i].sin_addr.s_addr != 0)
            continue;
        if(inet_pton(AF_INET, client, &(g_oscClient[i].sin_addr)) != 1) {
            g_oscClient[i].sin_addr.s_addr = 0;
            fprintf(stderr, "libzynaudioplayer: Failed to register client %s\n", client);
            return -1;
        }
        fprintf(stderr, "libzynaudioplayer: Added OSC client %d: %s\n", i, client);
        g_bOsc = 1;
        return i;
    }
    fprintf(stderr, "libzynaudioplayer: Not adding OSC client %s - Maximum client count reached [%d]\n", client, MAX_OSC_CLIENTS);
    return -1;
}

void removeOscClient(const char* client) {
    char pClient[sizeof(struct in_addr)];
    if(inet_pton(AF_INET, client, pClient) != 1)
        return;
    g_bOsc = 0;
    for(int i = 0; i < MAX_OSC_CLIENTS; ++i) {
        if(memcmp(pClient, &g_oscClient[i].sin_addr.s_addr, 4) == 0) {
            g_oscClient[i].sin_addr.s_addr = 0;
            fprintf(stderr, "libzynaudioplayer: Removed OSC client %d: %s\n", i, client);
        }
        if(g_oscClient[i].sin_addr.s_addr != 0)
            g_bOsc = 1;
    }
}
