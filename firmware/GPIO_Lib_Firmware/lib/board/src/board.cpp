#include "board.h"
#include "modules.h"
#include <stdio.h>
#include <string.h>

// Compose board identifier directly from the build flag.
// Expected format: BOARD=[PLATFORM]_[NAME] (e.g. BOARD=ESP32_T_DONGLE_S3).
#define BOARD_STR_HELPER(x) #x
#define BOARD_STR(x) BOARD_STR_HELPER(x)

const char *board_module_flags() {
    static char buf[128];
    buf[0] = '\0';

#if defined(BOARD)
    snprintf(buf, sizeof(buf), "BOARD=%s", BOARD_STR(BOARD));
#else
    snprintf(buf, sizeof(buf), "BOARD=GENERIC");
#endif

    return buf;
}

void board_init() {
    // Register board flag(s) as tokens (modules expects short strings)
    const char *s = board_module_flags();
    if (s && s[0]) {
        // split tokens on space and register each separately for clarity
        // simplest approach: register the full string and also split components
        // modules_add_flag(s);
        // register individual tokens if present
        // find first space
        const char *p = s;
        while (*p) {
            // find next space
            const char *sp = p;
            while (*sp && *sp != ' ') sp++;
            // copy token
            char tok[64];
            int len = (int)(sp - p);
            if (len > 0 && len < (int)sizeof(tok)) {
                memcpy(tok, p, (size_t)len);
                tok[len] = '\0';
                modules_add_flag(tok);
            }
            if (!*sp) break;
            p = sp + 1;
        }
    }
}
