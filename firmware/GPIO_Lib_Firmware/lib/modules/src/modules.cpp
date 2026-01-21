#include "modules.h"
#include <string.h>
#include <stdio.h>

#ifdef LARGE_BUFFERS
#define MAX_MODULE_FLAGS 24
#define MAX_FLAG_LEN 64
#else
#define MAX_MODULE_FLAGS 8
#define MAX_FLAG_LEN 32
#endif

static char g_flags[MAX_MODULE_FLAGS][MAX_FLAG_LEN];
static int g_flags_count = 0;

void modules_init() {
    g_flags_count = 0;
    for (int i = 0; i < MAX_MODULE_FLAGS; ++i) g_flags[i][0] = '\0';
}

bool modules_add_flag(const char *flag) {
    if (!flag) return false;
    if (g_flags_count >= MAX_MODULE_FLAGS) return false;
    // copy up to MAX_FLAG_LEN-1
    snprintf(g_flags[g_flags_count], MAX_FLAG_LEN, "%s", flag);
    g_flags_count++;
    return true;
}

uint16_t modules_get_flags(char *buf, uint16_t bufsize) {
    if (!buf || bufsize == 0) return 0;
    uint16_t pos = 0;
    for (int i = 0; i < g_flags_count; ++i) {
        const char *s = g_flags[i];
        for (int j = 0; s[j] != '\0'; ++j) {
            if (pos + 1 >= bufsize) { buf[pos] = '\0'; return pos; }
            buf[pos++] = s[j];
        }
            // separator (space)
            if (pos + 1 >= bufsize) { buf[pos] = '\0'; return pos; }
            buf[pos++] = ' ';
    }
    if (pos < bufsize) buf[pos] = '\0';
    return pos;
}
