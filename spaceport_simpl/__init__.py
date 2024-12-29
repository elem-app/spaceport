"""Default subject implementation package shipped with Spaceport."""

from spaceport.subject.impl_pkg import declare_impl_pkg

from .browser import BrowserFactory
from .container import ContainerFactory
from .dummy import DummySubject
from .fs import FS, FSFactory
from .repl import BashREPL
from .sdoc import SDocEditor

declare_impl_pkg(
    DummySubject,
    BashREPL,
    ContainerFactory,
    FS,
    FSFactory,
    SDocEditor,
    BrowserFactory,
)
