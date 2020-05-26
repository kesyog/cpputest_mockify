# CppUTest mockify

Easily generate mocks to be used with the [CppUTest mocking framework](https://cpputest.github.io/mocking_manual.html).
lowering the barrier to writing C unit tests. Interested in how this can help you? Check out
[this great post](https://interrupt.memfault.com/blog/unit-test-mocking) from the guys at [Memfault](https://github.com/memfault).

## Usage

To generate a .cpp mock file, run:

```
cpputest_mockify <input_file.h> <output directory>
```

Afterward, scan the output file for instances of `FIXME`, `CHECKME`, or `WRITEME`, indicating areas
where manual intervention is required.

## Benefits

* Stupid simple to use
* No external dependencies
* No need to configure include paths or otherwise tell it anything about your build
* Compatible with Python 2 and 3

## Drawbacks

In the end, the script boils down to a surprisingly-effective but very hacky regex 🤷

To keep usage (and the implementation) simple, it doesn't use a real C language parser (e.g.
[pycparser](https://github.com/eliben/pycparser)) so it's not to going to work reliably 100% of the
time. For example, array parameters aren't really handled well. In practice, on real code™, it will
get you ~80-90% of the way there and let you know when it needs further help.

The script doesn't currently do incremental mock generation. If you add a new function to your
header file, you're best off overwriting your old mock and relying on version control to manage the
changes.

## Other contributors

Thanks to [Noah Pendleton](https://github.com/noahp) and [Alan Rosenthal](https://github.com/AlanRosenthal)
for cleaning up my hacks and adding functionality. Also to <https://github.com/marco-m/mockify>, the
original inspiration for the script.

## Alternatives

* <https://github.com/marco-m/mockify>: uses pycparser to get a deeper understanding of your code.
* <https://github.com/jgonzalezdr/CppUMockGen>

