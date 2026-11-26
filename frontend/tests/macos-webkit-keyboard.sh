#!/bin/sh
# Enable Tab navigation to all controls for this WebKit process only.
exec "${WAYTOGO_KEYBOARD_WEBKIT:?Missing WebKit executable}" "$@" -AppleKeyboardUIMode 3
