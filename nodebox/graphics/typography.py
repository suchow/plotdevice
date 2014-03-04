# encoding: utf-8
from xml.parsers import expat
from operator import itemgetter, attrgetter
from nodebox.util import odict, ddict
from AppKit import *
from Foundation import *

from pprint import pprint

from nodebox import NodeBoxError
from nodebox.graphics.grobs import TransformMixin, ColorMixin, Color, Region, Size
from nodebox.graphics.grobs import _save, _restore, Transform, Grob, BezierPath
from nodebox.util.foundry import *

__all__ = ["Text", "Family", "Font", "Stylesheet", 
           "LEFT", "RIGHT", "CENTER", "JUSTIFY",
           "DEFAULT", ]

# text alignments
LEFT = "left"
RIGHT = "right"
CENTER = "center"
JUSTIFY = "justify"
_TEXT=dict(
    left = NSLeftTextAlignment,
    right = NSRightTextAlignment,
    center = NSCenterTextAlignment,
    justify = NSJustifiedTextAlignment
)

# hopefully non-conflicting style name for the stylesheet defaults
DEFAULT = '_p_l_o_t_d_e_v_i_c_e_'

class Singleton(type):
  def __init__(cls, name, bases, dict):
      super(Singleton, cls).__init__(name, bases, dict)
      cls.instance = None 

  def __call__(cls,*args,**kw):
      if cls.instance is None:
          cls.instance = super(Singleton, cls).__call__()
      cls.instance.render(*args, **kw)
      return cls.instance

class Typesetter(object):
    __metaclass__ = Singleton
    # collect nstext system objects
    store = NSTextStorage.alloc().init()
    layout = NSLayoutManager.alloc().init()
    column = NSTextContainer.alloc().init()

    # assemble nsmachinery
    layout.addTextContainer_(column)
    store.addLayoutManager_(layout)
    column.setLineFragmentPadding_(0)

    def render(cls, ctx, txt, inherit, styles, w=None, h=None):
        w,h = [d or 1000000 for d in w,h]

        # find any tagged regions that need styling
        parser = XMLParser(txt)

        # generate a Font for each unique cascade of style tags
        attrs = {seq:styles._cascade(inherit, *seq) for seq in sorted(parser.regions)}

        # convert the Fonts into attr dicts then apply them to the runs found in the parse
        astr = NSMutableAttributedString.alloc().initWithString_(parser.text)
        for cascade, runs in parser.regions.items():
            style = attrs[cascade]
            for rng in runs:
                astr.setAttributes_range_(style, rng)

        cls.store.beginEditing()
        cls.store.setAttributedString_(astr)
        cls.store.endEditing()
        cls.column.setContainerSize_((w,h))

        print '[[%s]]' % parser.text
        # print "colsize", cls.colsize
        # print "visible chars", cls.visible
        # print "typeblock", cls.typeblock
        cls.astr = astr

    def draw_glyphs(cls, x, y):
        cls.layout.drawGlyphsForGlyphRange_atPoint_(cls.visible, (x,y))

    @property
    def typeblock(cls):
        return Region(*cls.layout.boundingRectForGlyphRange_inTextContainer_(cls.visible, cls.column))

    @property
    def visible(cls):
        return cls.layout.glyphRangeForTextContainer_(cls.column)

    @property
    def colsize(cls):
        return Size(*cls.column.containerSize())

class Text(Grob, TransformMixin, ColorMixin):

    stateAttributes = ('_transform', '_transformmode', '_stylesheet', '_fillcolor', '_fontname', '_fontsize', '_align', '_lineheight')
    kwargs = ('fill', 'font', 'fontsize', 'align', 'lineheight')

    __dummy_color = NSColor.blackColor()
    
    def __init__(self, ctx, text, x=0, y=0, width=None, height=None, **kwargs):
        super(Text, self).__init__(ctx)
        TransformMixin.__init__(self)
        ColorMixin.__init__(self, **kwargs)
        self.text = unicode(text)
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self._fontname = kwargs.get('font', "Helvetica")
        self._fontsize = kwargs.get('fontsize', 24)
        self._lineheight = max(kwargs.get('lineheight', 1.2), 0.01)
        self._align = kwargs.get('align', LEFT)

    def copy(self):
        new = self.__class__(self._ctx, self.text)
        _copy_attrs(self, new,
            ('x', 'y', 'width', 'height', '_transform', '_transformmode', 
            '_fillcolor', '_fontname', '_fontsize', '_align', '_lineheight'))
        return new

    @property
    def font(self):
        return NSFont.fontWithName_size_(self._fontname, self._fontsize)

    def _draw(self):
        x,y = self.x, self.y
        # print "text w/", {nm:getattr(self, nm) for nm in Text.stateAttributes}

        rewrites = dict(face="_fontname", size="_fontsize", color="_fillcolor", align="_align", 
                        leading="_lineheight")
        inherit = {style:getattr(self, attr) for style,attr in rewrites.items()}
        print "draw w/", inherit

        printer = Typesetter(self._ctx, self.text, inherit, self._stylesheet, self.width, self.height)
        (dx, dy), (w, h) = printer.typeblock
        preferredWidth, preferredHeight = printer.colsize

        if self.width is not None:
            if self._align == RIGHT:
                x += preferredWidth - w
            elif self._align == CENTER:
                x += (preferredWidth-w)/2

        _save()
        # Center-mode transforms: translate to image center
        if self._transformmode == CENTER:
            deltaX = w / 2
            deltaY = h / 2
            t = Transform()
            t.translate(x+deltaX, y-self.font.defaultLineHeightForFont()+deltaY)
            t.concat()
            self._transform.concat()
            printer.draw_glyphs(-deltaX-dx, -deltaY-dy)
        else:
            self._transform.concat()
            printer.draw_glyphs(x-dx, y-dy-self.font.defaultLineHeightForFont())
        _restore()
        return (w, h)

    @property
    def metrics(self):
        rewrites = dict(face="_fontname", size="_fontsize", color="_fillcolor", align="_align", 
                        leading="_lineheight")
        inherit = {style:getattr(self, attr) for style,attr in rewrites.items()}
        print "metrics w/", inherit
        printer = Typesetter(self._ctx, self.text, inherit, self._stylesheet, self.width, self.height)
        return printer.typeblock.size

    @property
    def path(self):
        rewrites = dict(face="_fontname", size="_fontsize", color="_fillcolor", align="_align", 
                        leading="_lineheight")
        inherit = {style:getattr(self, attr) for style,attr in rewrites.items()}
        print "path w/", inherit
        x,y = self.x, self.y
        printer = Typesetter(self._ctx, self.text, inherit, self._stylesheet, self.width, self.height)
        (dx, dy), (w, h) = printer.typeblock
        preferredWidth, preferredHeight = printer.colsize

        if self.width is not None:
           if self._align == RIGHT:
               x += preferredWidth - w
           elif self._align == CENTER:
               x += preferredWidth/2 - w/2
        length = printer.layout.numberOfGlyphs()
        path = NSBezierPath.bezierPath()
        for glyphIndex in range(length):
            txtIndex = printer.layout.characterIndexForGlyphAtIndex_(glyphIndex)
            txtFont, txtRng = printer.store.attribute_atIndex_effectiveRange_("NSFont", txtIndex, None)
            lineFragmentRect, _ = printer.layout.lineFragmentRectForGlyphAtIndex_effectiveRange_(glyphIndex, None)

            # Here layoutLocation is the location (in container coordinates) where the glyph was laid out. 
            layoutPoint = printer.layout.locationForGlyphAtIndex_(glyphIndex)
            finalPoint = [lineFragmentRect[0][0],lineFragmentRect[0][1]]
            finalPoint[0] += layoutPoint[0] - dx
            finalPoint[1] += layoutPoint[1] - dy
            g = printer.layout.glyphAtIndex_(glyphIndex)
            if g == 0: continue
            path.moveToPoint_((finalPoint[0], -finalPoint[1]))
            path.appendBezierPathWithGlyph_inFont_(g, txtFont)
            path.closePath()
        path = BezierPath(self._ctx, path)
        trans = Transform()
        trans.translate(x,y-self.font.defaultLineHeightForFont())
        trans.scale(1.0,-1.0)
        path = trans.transformBezierPath(path)
        path.inheritFromContext()
        return path

class XMLParser(object):
    _log = 0

    def __init__(self, txt):
        p = expat.ParserCreate()
        p.StartElementHandler = self._enter
        p.EndElementHandler = self._leave
        p.CharacterDataHandler = self._chars
        self._expat = p
        if isinstance(txt, unicode):
            txt = txt.encode('utf-8')
        wrap = "<%s>" % ">%s</".join([DEFAULT]*2)
        self.xml = wrap % txt
        self.text = None

    @property
    def regions(self):
        if self.text is None:
            try:
                self.stack = []
                self.cursor = 0
                self.runs = ddict(list)
                self.body = []
                self._expat.Parse(self.xml, True)
            except expat.ExpatError, e:
                # go a little overboard providing context for syntax errors
                print '%r'%xml
                raise e
                line = xml.split('\n')[e.lineno-1]
                self._expat_error(e, line)
            self.text = "".join(self.body)

        return self.runs

    def _expat_error(self, e, line):
        measure = 80
        col = e.offset
        start, end = len('<%s>'%DEFAULT), -len('</%s>'%DEFAULT)
        line = line[start:end]
        col -= start

        # move the column range with the typo into `measure` chars
        snippet = line
        if col>measure:
            snippet = snippet[col-measure:]
            col -= col-measure
        snippet = snippet[:max(col+12, measure-col)]
        
        # show which ends of the line are truncated
        clipped = [snippet]
        if not line.endswith(snippet):
            clipped.append('...')
        if not line.startswith(snippet):
            clipped.insert(0, '...')
            col+=3
        caret = ' '*col + '^'

        # raise the exception
        msg = 'Text: ' + "\n".join(e.args)
        stack = 'stack: ' + " ".join(['<%s>'%tag for tag in self.stack[1:]]) + ' ...'
        xmlfail = "\n".join([msg, "".join(clipped), caret, stack])
        raise NodeBoxError(xmlfail)

    def log(self, s=None, indent=0):
        if not isinstance(s, basestring):
            if s is None:
                return self._log
            self._log = int(s)
            return
        if not self._log: return
        if indent<0: self._log-=1
        msg = (u'  '*self._log)+(s if s.startswith('<') else repr(s))
        print msg.encode('utf-8')
        if indent>0: self._log+=1

    def _enter(self, name, attrs):
        self.stack.append(name)
        self.log(u'<%s>'%(name), indent=1)

    def _leave(self, name):
        if name == DEFAULT: 
            self.body = u"".join(self.body)
        self.stack.pop()
        self.log(u'</%s>'%(name), indent=-1)

    def _chars(self, data):
        self.runs[tuple(self.stack)].append(tuple([self.cursor, len(data)]))
        self.cursor += len(data)
        self.body.append(data)
        self.log(u'"%s"'%(data))






class Stylesheet(object):
    kwargs = ('family','size','leading','weight','width','variant','italic','heavier','lighter','color','face','fontname','fontsize','lineheight')

    def __init__(self, ctx, styles=None):
        self._ctx = ctx
        self._styles = dict(styles or {})

    def __repr__(self):
        styles = repr({k.replace(DEFAULT,'DEFAULT'):v for k,v in self._styles.items() if k is not DEFAULT})
        if DEFAULT in self._styles:
            styles = '{DEFAULT: %r, '%self._styles[DEFAULT] + styles[1:]
        return "Stylesheet(%s)"%(styles)

    def __iter__(self):
        return iter(self._styles.keys())

    def __len__(self):
        return len(self._styles)

    def __getitem__(self, key):
        item = self._styles.get(key)
        return dict(item) if item else None

    def __setitem__(self, key, val):
        if val is None:
            del self[key]
        elif hasattr(val, 'items'):
            self.style(key, **val)
        else:
            badtype = 'Stylesheet: when directly assigning styles, pass them as dictionaries (not %s)'%type(val)
            raise NodeBoxError(badtype)

    def __delitem__(self, key):
        if key in self._styles:
            del self._styles[key]

    def copy(self):
        new = self.__class__(self._ctx, self._styles)
        return new
    
    @property
    def styles(self):
        return dict(self._styles)

    def style(self, name, *args, **kwargs):
        if not kwargs and any(a in (None,'inherit') for a in args[:1]):
            del self[name]
        elif args or kwargs:
            spec = Stylesheet._spec(*args, **kwargs)
            color = kwargs.get('color')
            if color and not isinstance(color, Color):
                if isinstance(color, basestring):
                    color = (color,)
                color = Color(self._ctx, *color)
            if color:
                spec['color'] = color
            self._styles[name] = spec
        return self[name]

    def _cascade(self, inherit, *styles):
        """Apply the listed styles in order and return nsattibutedstring attrs"""
        
        # use the context's font and color settings unless the DEFAULT style has overrides
        # inherit = dict(face="_fontname", size="_fontsize", color="_fillcolor",
        #                 align="_align", leading="_lineheight")
        # spec = {style:getattr(self._ctx, attr) for style,attr in inherit.items()}
        # print 'inheritance', inherit
        spec = dict(inherit)
        print 'inherited', spec
        spec.update(self._styles.get(DEFAULT,{}))

        # layer the styles to generate a final font and color
        for tag in styles:
            spec.update(self._styles.get(tag,{}))

        # OOPS: what about transparent fills? 
        if spec.get('color') is None:
            color = Color._nscolor('grey',0,0)
        else:
            color = Color(self._ctx, spec.pop('color')).nsColor
        alignment = _TEXT[spec['align']]

        graf = NSMutableParagraphStyle.alloc().init()
        graf.setLineBreakMode_(NSLineBreakByWordWrapping)
        graf.setAlignment_(alignment)
        graf.setLineHeightMultiple_(spec['leading'])
        # graf.setLineSpacing_(extra_px_of_lead)
        # graf.setParagraphSpacing_(1em?)
        # graf.setMinimumLineHeight_(self._lineheight)

        font = Font(self._ctx, **{k:v for k,v in spec.items() if k in Stylesheet.kwargs} )
        print font.name, color, spec.get('color')
        return {"NSFont":font._nsFont, "NSColor":color, NSParagraphStyleAttributeName:graf}

    @classmethod
    def _spec(cls, *args, **kwargs):
        badargs = [k for k in kwargs if k not in Stylesheet.kwargs]
        if badargs:
            eg = '"'+'", "'.join(badargs)+'"'
            badarg = 'unknown keyword argument%s for font style: %s'%('' if len(badargs)==1 else 's', eg)
            raise NodeBoxError(badarg)

        # start with kwarg values as the canonical settings
        _canon = ('family','size','weight','italic','width','variant','leading','color')
        spec = {k:v for k,v in kwargs.items() if k in _canon}

        # be backward compatible with the old arg names
        if 'fontsize' in kwargs: 
            spec.setdefault('size', kwargs['fontsize'])
        if 'fill' in kwargs: 
            spec.setdefault('color', kwargs['fill'])
        if 'lineheight' in kwargs: 
            spec.setdefault('leading', kwargs['lineheight'])

        # look for a postscript name passed as `face` or `fontname` and validate it
        basis = kwargs.get('face', kwargs.get('fontname'))
        if basis and not font_exists(basis):
            notfound = 'Font: no matches for Postscript name "%s"'%basis
            raise NodeBoxError(badarg)
        elif basis:
            spec['face'] = basis



        # TODO
        # should also serialize colors somehow. maybe just as tuples...



        # allow for negative values in the weight step params, but
        # normalize them in the spec
        mod = int(kwargs.get('heavier', -kwargs.get('lighter', 0)))
        if mod:
            direction = 'lighter' if mod < 0 else 'heavier'
            spec[direction] = abs(mod)

        # search the positional args for either name/size or a Font object
        # we want the kwargs to have higher priority, so setdefault everywhere...
        for item in args:
            if isinstance(item, Face):
                spec.setdefault('face', item)
            if isinstance(item, Font):
                spec.setdefault('face', item._face)
                spec.setdefault('size', item._size)
            elif isinstance(item, basestring):
                if facey(item):
                    spec.setdefault('face', item)
                elif widthy(item):
                    spec.setdefault('width', item)
                elif weighty(item):
                    spec.setdefault('weight', item)
                elif fammy(item):
                    spec.setdefault('family', family_name(item))
                else:
                    print 'No clue what to make of "%s"'%item
            elif isinstance(item, (int, float, long)):
                spec.setdefault('size', item)
        return spec



    def test(self, txt):
        print Typesetter(self._ctx, txt, self).astr

# UIFontDescriptor* desc =
#     [UIFontDescriptor fontDescriptorWithName:@"Didot" size:18];
#     NSArray* arr =
#     @[@{UIFontFeatureTypeIdentifierKey:@(kLetterCaseType),
#         UIFontFeatureSelectorIdentifierKey:@(kSmallCapsSelector)}];
#     desc =
#     [desc fontDescriptorByAddingAttributes:
#      @{UIFontDescriptorFeatureSettingsAttribute:arr}];
#     UIFont* f = [UIFont fontWithDescriptor:desc size:0];

class Font(object):

    def __init__(self, ctx, *args, **kwargs):
        # normalize the names of the keyword args and do fuzzy matching on positional args
        # to create a specification with just the valid keys
        spec = Stylesheet._spec(*args, **kwargs)

        # initialize our internals based on the spec
        self._ctx = ctx
        if 'face' not in spec or any(arg not in ('face','size') for arg in spec):
            # we only need to search if no face arg was supplied or if there are 
            # style modifications to be applied on top of it
            self._update_face(**spec)
        else:
            self._face = font_face(spec['face'])

        # BUG: probably don't want to inherit this immediately...
        self._size = float(spec.get('size', ctx._fontsize))

    def __enter__(self):
        if hasattr(self, '_prior'):
            self._rollback = self._prior
            del self._prior
        else:
            self._rollback = self._get_ctx()
        self._update_ctx()
        return self

    def __exit__(self, type, value, tb):
        self._update_ctx(*self._rollback)

    def __repr__(self):
        spec = (u'"%(family)s"|-|%(weight)s|-|<%(psname)s>'%(self._face._asdict())).split('|-|')
        if self._face.variant:
            spec.insert(2, self._face.variant)
        spec.insert(1, '/' if self._face.italic else '|')
        if self._size:
            spec.insert(1, ("%rpt"%self._size).replace('.0pt','pt'))
        return (u'Font(%s)'%" ".join(spec)).encode('utf-8')

    def __call__(self, *args, **kwargs):
        return Font(self._ctx, self, *args, **kwargs)

    def _get_ctx(self):
        return (self._ctx._fontname, self._ctx._fontsize)

    def _update_ctx(self, face=None, size=None):
        face, size = (face or self.face), (size or self.size)
        self._ctx._fontname, self._ctx._fontsize = face, size

    def _update_face(self, **spec):
        # use the basis kwarg (or this _face if omitted) as a starting point
        basis = spec.get('face', getattr(self,'_face', self._ctx._fontname))
        if isinstance(basis, basestring):
            basis = font_face(basis)

        # if there weren't any args to fine tune the fam/weight/width/variant, just 
        # use the basis Face as is and bail out
        if not {'family','weight','width','variant','italic'}.intersection(spec):
            self._face = basis
            return

        # otherwise try to find the best match for the new attributes within either
        # the family in the spec, or the current family if omitted
        try:
            spec['face'] = basis
            fam = Family(self._ctx, spec.get('family', basis.family))
            candidates, scores = zip(*fam.select(spec).items())
            self._face = candidates[0]
        except IndexError:
              nomatch = "Font: couldn't find a face matching criteria %r"%spec
              raise NodeBoxError(nomatch)

    def _use(self):
        # called right after allocation by the font() command. remembers the font state
        # from before applying itself since by the time __enter__ takes a snapshot the 
        # prior state will already be overwritten
        self._prior = self._get_ctx()
        self._update_ctx()
        return self

    @property
    def _nsFont(self):
        return NSFont.fontWithName_size_(self._face.psname, self._size)

    @property
    def _nsColor(self):
        return self._ctx._fillcolor.nsColor

    # .name
    def _get_name(self):
        return self._face.family
    def _set_name(self, f):
        self.family = f
    name = property(_get_name, _set_name)

    # .family
    def _get_family(self):
        return Family(self._ctx, self._face.family)
    def _set_family(self, f):
        if isinstance(f, Family):
            f = f.name
        self._update_face(family=family_name(f))
    family = property(_get_family, _set_family)

    # .weight
    def _get_weight(self):
        return self._face.weight
    def _set_weight(self, w):
        self._update_face(weight=w)
    weight = property(_get_weight, _set_weight)

    # .width
    def _get_width(self):
        return self._face.width
    def _set_width(self, w):
        self._update_face(width=w)
    width = property(_get_width, _set_width)

    # .variant
    def _get_variant(self):
        return self._face.variant
    def _set_variant(self, v):
        self._update_face(variant=v)
    variant = property(_get_variant, _set_variant)

    # .size
    def _get_size(self):
        return self._size
    def _set_size(self, s):
        self._size = float(s)
    size = property(_get_size, _set_size)

    # .italic
    def _get_italic(self):
        return self._face.italic
    def _set_italic(self, ital):
        if ital != self.italic:
            self._update_face(italic=ital)
    italic = property(_get_italic, _set_italic)

    # .face
    def _get_face(self):
        return self._face.psname
    def _set_face(self, face):
        self._face = font_face(face)
    face = property(_get_face, _set_face)

    @property
    def traits(self):
        return self._face.traits

    @property
    def weights(self):
        return self.family.weights

    @property
    def widths(self):
        return self.family.widths

    @property
    def variants(self):
        return self.family.variants

    @property
    def siblings(self):
        return self.family.fonts

    def heavier(self, steps=1):
        self.modulate(steps)

    def lighter(self, steps=1):
        self.modulate(-steps)

    def modulate(self, steps):
        if not steps: 
            return
        seq = self.weights
        idx = seq.index(self.weight)
        less, more = list(reversed(seq[:idx+1])), seq[idx:]
        if steps<0:
            match = less[abs(steps):abs(steps)+1] or [less[-1]]
        elif steps>0:
            match = more[steps:steps+1] or [more[-1]]
        self.weight = match[0]

class Family(object):
    def __init__(self, ctx, famname=None, of=None):
        self._ctx = ctx
        if of:
            famname = font_family(of)
        elif not famname:
            badarg = 'Family: requires either a name or a Font object'%famname
            raise NodeBoxError(badarg)

        q = famname.strip().lower().replace(' ','')
        matches = [fam for fam in family_names() if q==fam.lower().replace(' ','')]
        if not matches:
            notfound = 'Unknown font family "%s"'%famname
            raise NodeBoxError(notfound)
        self._name = matches[0]

        faces = family_members(self._name)
        self.encoding = font_encoding(faces[0].psname)
        self._faces = odict( (f.psname,f) for f in faces )

        fam = {"weights":[], "widths":[], "variants":[]}
        has_italic = False
        for f in sorted(faces, key=attrgetter('wgt')):
            for axis in ('weights','variants'):
                old, new = fam[axis], getattr(f,axis[:-1])
                if new not in old:
                    fam[axis].append(new)
            has_italic = has_italic or 'italic' in f.traits
        self.has_italic = has_italic

        for f in sorted(faces, key=attrgetter('wid')):
            if f.width in fam['widths']: continue
            fam['widths'].append(f.width)

        for axis, vals in fam.items():
            if axis in ('widths','variants') and any(vals) and None in vals:
                if axis=='widths':
                    pass # for widths, the default should be preserved in sort order
                else:
                    # for variants, default should be first
                    fam[axis] = [None] + filter(None,vals)
            else:
                fam[axis] = filter(None,vals) # otherwise wipe out the sole None
            setattr(self, axis, tuple(fam[axis]))

    def __repr__(self):
        contents = ['"%s"'%self._name, ]
        for group in 'weights', 'widths', 'variants', 'faces':
            n = len(getattr(self, group))
            if n:
                contents.append('%i %s%s' % (n, group[:-1], '' if n==1 else 's'))
        return (u'Family(%s)'%", ".join(contents)).encode('utf-8')

    @property
    def name(self):
        return self._name

    @property
    def faces(self):
        return odict(self._faces)

    @property
    def fonts(self):
        return odict( (k,Font(self._ctx, v)) for k,v in self._faces.items())

    def select(self, spec):
        current = spec.get('face', self._ctx._fontname)
        if isinstance(current, basestring):
            current = font_face(current)

        axes = ('weight','width','italic','variant')
        opts = {k:v for k,v in spec.items() if k in axes}
        defaults = dict( (k, getattr(current, k)) for k in axes + ('wid', 'wgt'))
        
        # map the requested weight/width onto what's available in the family
        w_spans = {"wgt":[1,14], "wid":[-15,15]}
        for axis, num_axis in dict(weight='wgt', width='wid').items():
            w_vals = [getattr(f, num_axis) for f in self._faces.values()]
            w_spans[num_axis] = [min(w_vals), max(w_vals)]
            dst = opts if axis in opts else defaults
            wname, wval = self._closest(axis, opts.get(axis, getattr(current,axis)))
            dst.update({axis:wname, num_axis:wval})

        def score(axis, f):
            bonus = 2 if axis in opts else 1
            val = opts[axis] if axis in opts else defaults.get(axis)
            vs = getattr(f,axis)
            if axis in ('wgt','wid'):
                w_min, w_max = w_spans[axis]
                agree = 1 if val==vs else -abs(val-vs) / float(max(w_max-w_min, 1))
            elif axis in ('weight','width'):
                # agree = 1 if (val or None) == (vs or None) else 0
                agree = 0
            else:
                agree = 1 if (val or None) == (vs or None) else -1
            return agree * bonus

        scores = ddict(int)
        for f in self.faces.values():
            # consider = 'italic', 'weight', 'width', 'variant', 'wgt', 'wid'
            # print [score(axis,f) for axis in consider], [getattr(f,axis) for axis in consider]
            scores[f] += sum([score(axis,f) for axis in 'italic', 'weight', 'width', 'variant', 'wgt', 'wid'])

        candidates = [dict(score=s, face=f, ps=f.psname) for f,s in scores.items()]
        candidates.sort(key=itemgetter('ps'))
        candidates.sort(key=itemgetter('score'), reverse=True)
        # for c in candidates[:10]:
        #     print "  %0.2f"%c['score'], c['face']
        return odict( (c['face'],c['score']) for c in candidates)

    def _closest(self, axis, val):
        # validate the width/weight string and make sure it either conforms to the 
        # family's names, or can be turned into an std. integer value
        num_axis = dict(weight='wgt', width='wid')[axis]
        corpus = {getattr(f,axis):getattr(f,num_axis) for f in self._faces.values()}
        w_names, w_vals = corpus.keys(), corpus.values()

        if sanitized(val) in sanitized(w_names):
            wname = w_names[sanitized(w_names).index(sanitized(val))]
            return wname, corpus[wname]

        # if the name doesn't exist in the family, find its standard name/num values 
        # then truncate them by the range of the face (so e.g., asking for `obese' will 
        # only turn into `semibold' if that's as heavy as the family gets)
        wname, wval = standardized(axis, val)
        wval = max(min(w_vals), min(max(w_vals), wval))
        if wval in w_vals:
            wname = w_names[w_vals.index(wval)]
        return wname, wval

if __name__=='__main__':
    test()

