'''
dps by Dr. Jekyll
1.0 Release

Description: shows your damage per second and the highest dps you reached,
in the bottom right corner just above the zone name. both reset when the map
changes.

How it works: your damage is read from the hit numbers the game draws for your
hits. each number is counted once; if a number on screen grows (hits merged
into it), the increase is added. dps is the damage dealt in the last `window`
seconds divided by `window`. max is the highest dps seen; it goes back to 0
after `max_reset` seconds without a hit.

If you want to customize it paste this into config.ini:

[plugin_dps]
enabled = yes
# seconds of damage averaged into the dps
window = 5
# max goes back to 0 after this many seconds without a hit (0 = never)
max_reset = 5
# text size
size = 16
# distance from the bottom of the window to the bottom of the dps line
y = 26
color_dps = ffffff60
color_max = ffff6040
'''

import collections
import time

from _remote import ffi
from manager import PluginBase
import util

# HitNumberGraphic::NumType values for numbers from your hits on enemies
SELF_DAMAGE_TYPES = (2, 4, 6)  # attack, crit, armor


class Plugin(PluginBase):
    def onInit(self):
        self.config.option('window', 5, 'float')
        self.config.option('max_reset', 5, 'float')
        self.config.option('size', 16, 'int')
        self.config.option('y', 26, 'int')
        self.config.option('color_dps', 0xffffff60, 'color')
        self.config.option('color_max', 0xffff6040, 'color')

        self.dpsTxt = util.PlainText(font='HemiHeadBold')
        self.maxTxt = util.PlainText(font='HemiHeadBold')
        self.reset(None)

    def reset(self, key):
        self.mapKey = key
        self.hits = collections.deque()  # (time, damage)
        self.inWindow = 0
        self.numbers = {}                # (address, startTime, type) -> value counted
        self.dps = 0.0
        self.max = 0.0
        self.lastHit = None

    def afterUpdate(self):
        cw = self.refs.ClientWorld
        if cw == ffi.NULL:
            return
        wp = cw.asWorld.props
        zone = util.getstr(wp.zone) if wp.zone != ffi.NULL else ''
        key = (int(ffi.cast('uintptr_t', cw)), cw.asWorld.id, zone, wp.floor)
        if key != self.mapKey:
            self.reset(key)

        now = time.perf_counter()
        wv = self.refs.WorldView
        if wv != ffi.NULL:
            seen = {}
            for g in util.vec2list(wv.dynamicGraphics, 'struct DynamicGraphic *'):
                if g == ffi.NULL or util.getClassName(g) != 'HitNumberGraphic':
                    continue
                h = ffi.cast('struct HitNumberGraphic *', g)
                if h.nt not in SELF_DAMAGE_TYPES or h.numTexture == ffi.NULL:
                    continue
                k = (int(ffi.cast('uintptr_t', g)), h.startTime, h.nt)
                val = h.numTexture.value
                before = self.numbers.get(k, 0)
                seen[k] = max(val, before)
                if val > before:
                    self.hits.append((now, val - before))
                    self.inWindow += val - before
                    self.lastHit = now
            self.numbers = seen

        window = max(0.1, self.config.window)
        while self.hits and self.hits[0][0] < now - window:
            self.inWindow -= self.hits.popleft()[1]
        self.dps = self.inWindow / window
        self.max = max(self.max, self.dps)
        gap = self.config.max_reset
        if gap > 0 and self.lastHit is not None and now - self.lastHit > gap:
            self.max = 0.0
            self.lastHit = None

    def onPresent(self):
        if self.refs.ClientWorld == ffi.NULL:
            return

        for t in (self.dpsTxt, self.maxTxt):
            t.size = self.config.size
        self.dpsTxt.color = self.config.color_dps
        self.maxTxt.color = self.config.color_max
        self.dpsTxt.text = 'DPS {:.0f}'.format(self.dps)
        self.maxTxt.text = 'MAX {:.0f}'.format(self.max)

        x = self.refs.windowW - 4
        y = self.refs.windowH - self.config.y
        self.dpsTxt.draw(x, y, anchorX=1, anchorY=1)
        self.maxTxt.draw(x, y - self.dpsTxt.h, anchorX=1, anchorY=1)
