from __future__ import annotations

"""The Guide's text: how to use LatencyLab, shortest path first.

Separate from the dialog for the same reason `about_text` is separate from
`about_dialog`: the words change far more often than the widget does, and a
change to the words should not be a change to a file full of Qt.

HTML rather than plain text, because this is a structured document with an
order that matters, and because `auto_scroller` needs a surface that scrolls in
PIXELS: a QTextBrowser does, a QPlainTextEdit scrolls in lines.

Written shortest-path-first on purpose. Somebody opening this has the
application in front of them and wants to make it do something in the next
minute, so the first section is six steps with no explanation attached, and
every reason for anything comes later, once there is something to attach the
reason to.
"""

GUIDE_TITLE = "Guide to LatencyLab"

# The lead-in, before the numbered start. Kept short: it is the only thing
# between the reader and the first instruction.
_INTRO = """
<h2>Guide to LatencyLab</h2>
<p>LatencyLab runs an explicit model of a system many times over and shows you
how long the user waited, and why. It does not measure your code. It lets you
argue about structure before there is any code to measure.</p>
<p>If you have never opened it before, do the six steps below first. Everything
after them is reasons, and reasons are easier once something has run.</p>
"""

_FIRST_RUN = """
<h3>1. Run something, in six steps</h3>
<ol>
<li>Open the <b>Examples</b> menu and choose <b>Checkout</b>. The Run button
flashes twice to say it is ready.</li>
<li>Leave <b>Runs</b> at 200 and <b>Seed</b> at 1 for now.</li>
<li>Press <b>Run</b>.</li>
<li>Read <b>Summary</b> on the left: the percentiles of the makespan, which is
how long the whole piece of work took.</li>
<li>Read <b>Critical path</b> beside it: the chain of work that actually held
the run up.</li>
<li>Press the <b>application mark</b> in the middle of the toolbar to open
<b>Distributions</b>, and look at the shape rather than at any one number.</li>
</ol>
<p>That is the whole loop. Everything else is variations on it.</p>
"""

_WHAT_YOU_SEE = """
<h3>2. What you are looking at</h3>
<p>The <b>makespan distribution</b> is a shape, not a target. Real systems are
stochastic, so a single run is not representative of anything and the spread is
the finding.</p>
<p>The <b>critical path</b> is not "what was slow". It is the chain that
prevented progress in that run. Expensive work that was not on it did not delay
anyone, however costly it looks in isolation.</p>
<p><b>Critical path frequency</b> counts how often each chain was the one
holding things up. A path that dominates is a behavioural mode: it describes how
the system usually behaves, and it is the only kind of path worth designing
against. The rest are a long tail.</p>
<p>The <b>info</b> button next to this one opens a longer piece on reading the
output, and it is worth reading once you have a run in front of you.</p>
"""

_CHANGE_SOMETHING = """
<h3>3. Change it and run it again</h3>
<p>One run tells you very little. Two runs of two structures is where the tool
starts earning its keep.</p>
<ol>
<li>With a model loaded, press <b>Edit</b> in the toolbar. The composer opens
with that model already in it.</li>
<li>Pick something in the left-hand list and change one thing. Raising a
context's <b>concurrency</b> from 1 to 2 is the clearest first experiment.</li>
<li>Press <b>Export + Load Into Main UI</b>, then <b>Run</b> again with the
<b>same seed</b>.</li>
<li>Compare the percentiles and the dominant path against what you had.</li>
</ol>
<p>Change one thing at a time. Two changes and a different answer tells you
nothing about which one did it.</p>
"""

_COMPOSING = """
<h3>4. Writing a model from nothing</h3>
<p>Press <b>Compose</b>. The composer lists the four parts of a model down the
left; work down them in order, because each one uses the one before it.</p>
<p><b>System</b> names the model and sets the <b>entry event</b>, which is the
thing that starts a run. Everything that happens is downstream of it.</p>
<p><b>Contexts</b> are what work runs on: a thread pool, a database, a browser
main thread. The only setting is <b>concurrency</b>, meaning how many tasks in
that context can be in flight at once. This is where queueing comes from, and
it is the single most under-modelled thing in most systems.</p>
<p><b>Tasks</b> are units of work. Each one names the context it runs in, how
long it takes as a <b>distribution</b>, and the events it <b>emits</b> when it
finishes.</p>
<p><b>Wiring</b> connects events to tasks: when this event happens, run that
task, optionally after a <b>delay</b>. Wiring is where the structure lives, so
it is the part worth arguing about.</p>
<p>Then <b>Validate</b>, and <b>Export</b> when it says so. Export writes the
JSON; Export and Load runs it straight away.</p>
"""

_WHY_SETTINGS = """
<h3>5. Why you would choose each setting</h3>

<p><b>Runs.</b> Each run is one draw from the model. 200 is enough to see the
shape and to compare two structures. If you intend to say something about p99,
you need enough runs that the tail is not three lucky samples: think in
thousands, and remember the tail is the part that moves most between run sets.</p>

<p><b>Seed.</b> The same model and the same seed give the same answer, every
time, on any machine. Hold the seed steady while you compare two structures, so
the difference you see is the structure. Then change it and re-run, to check the
difference was not an artefact of one draw.</p>

<p><b>Concurrency.</b> Set it to the number of things that genuinely happen at
once. A concurrency of 1 is a resource that serialises everything sent to it,
which is what a single database connection or a single UI thread actually is,
and it is where queues form. Raising it is the cheapest experiment in the tool
and often the most revealing.</p>

<p><b>Which distribution.</b> <b>Fixed</b> when the duration genuinely does not
vary, which is rarer than people assume and is honest mainly for a deliberate
delay. <b>Normal</b> when the work varies symmetrically around a typical value.
<b>Lognormal</b> for almost anything involving IO, a network or contention: it
is skewed, with a long right tail, which is what a slow request actually looks
like. Choosing normal for network work is how a model comes out far too
optimistic at p99.</p>

<p><b>Delays on wiring.</b> A delay is a deliberate wait: a debounce, a retry
backoff, a poll interval, a politeness pause. Model them, because they are
frequently the thing that owns the median while everyone is looking at the
database. The shipped Checkout example is exactly that: a 150ms debounce added
for politeness turns out to be the critical path in most runs.</p>

<p><b>Category.</b> A label on a task, for grouping the output. Useful once a
model is large enough that the critical path lists names you have to look
up.</p>

<p><b>Stress multiplier.</b> Generates a variant with every duration multiplied,
so you can ask what happens when everything is twice as slow. Structure that
holds up under stress is different from structure that only works when nothing
goes wrong, and the difference does not show at normal speed.</p>
"""

_HONESTY = """
<h3>6. Reading the answer honestly</h3>
<p>Name the dominant behaviour before proposing any fix. If a task never appears
on a dominant path, making it faster changes nothing anybody experiences.</p>
<p>Percentiles describe exposure, not goals. Lowering one without understanding
the shape usually moves the cost somewhere else rather than removing it.</p>
<p>The long tail can usually be left alone, unless you are designing for a
strict worst case. Optimising rare worst cases is how systems get complicated
without getting faster.</p>
<p>And the honest limit: LatencyLab tells you what a model does, not whether the
model is right. It is a way of making an argument checkable, not a way of
avoiding having one.</p>
"""

GUIDE_HTML = (
    _INTRO
    + _FIRST_RUN
    + _WHAT_YOU_SEE
    + _CHANGE_SOMETHING
    + _COMPOSING
    + _WHY_SETTINGS
    + _HONESTY
)
