import string, re, urllib
from string import split,join,find,lower,rfind,atoi,strip,lstrip
from urllib import quote, unquote

from Products.ZWiki.Utils import BLATHER, html_quote, html_unquote, formattedTraceback, \
     ZOPEVERSION
from Products.ZWiki.PurpleNumbers import add_purple_numbers_to
from Products.ZWiki.Regexps import dtmlorsgmlexpr, footnoteexpr
from Products.ZWiki.I18nSupport import _

# XXX temporary hack, used for placing subtopics in the page. Supposed to
# be secret, invisible, and never encountered by users. Ha!
MIDSECTIONMARKER = 'ZWIKIMIDSECTION'

#from AccessControl import getSecurityManager
#getSecurityManager().declarePublic('yes')
#getSecurityManager().declarePublic('no')
def yes(self): return 1
def no(self): return 0


class AbstractPageType:
    """
    I encapsulate behaviour which is specific to different zwiki page types.

    I'm an abstract class providing a number of methods which are
    page-type-specific, with default implementations. Override me and
    define _id and _name to make a usable page type object. See
    __init__.py for more.
    """

    _id = None
    _name = None
    supportsStx = no
    supportsRst = no
    supportsWwml = no
    supportsWikiLinks = no
    supportsHtml = no
    supportsDtml = no
    supportsEpoz = no

    def id(self): return self._id
    def name(self): return self._name
    __call__ = id

    def __repr__(self):
        return "<%s '%s (%s)' at 0x%s>" % (self.__class__.__name__,
                                           self.id(),
                                           self.name(),
                                           hex(id(self))[2:])

    def preRender(self,page,text=None):
        """
        Do all the pre-rendering we can for page, or for a piece of text.
        """
        return text or page.read()

    def render(self, page, REQUEST={}, RESPONSE=None, **kw):
        """
        Do any final (view-time) rendering for page.
        """
        return page.preRendered()

    def preRenderMessages(self,page):
        t = ''
        for m in page.messages(): t += self.preRenderMessage(page,m)
        if t: t = self.discussionSeparator(page) + t
        return t

    def preRenderMessage(self,page,msg):
        t = msg.get_payload()
        t = self.escapeEmailAddresses(page,t)
        t = self.renderCitationsIn(page,t)
        t = self.addCommentHeadingTo(page,t,msg)
        return t

    def escapeEmailAddresses(self,page,text):
        return re.sub(r'(?<!mailto:)\b(?!msg\d{14}-\d{4})(?<!msg\d{14}-)(\w[\w\-\+\.]*)@([\w\-\.]+)\.([\w\-\.]+)\b([^>]*<|$)', 
            lambda m: '<span class="nospam1">&#' + str(ord(m.groups()[0][0])) 
                + m.groups()[0][1:] 
                + '<!-- foobar --></span>&#64;<span class="nospam2">' 
                + m.groups()[1][0:-1] + '&#' + str(ord(m.groups()[1][-1])) 
                + ';&#46;' + m.groups()[2] + '</span>' + m.groups()[3], text)

    def renderCitationsIn(self,page,text):
        return text

    def addCommentHeadingTo(self,page,text,msg):
        return self.makeCommentHeading(page,
                                       msg.get('subject'),
                                       msg.get('from'),
                                       msg.get('date'),
                                       msg.get('message-id'),
                                       msg.get('in-reply-to')
                                       ) + text

    def makeCommentHeading(self, page,
                           subject, username, time, 
                           message_id=None,in_reply_to=None):
        heading = '\n\n'
        heading += '%s --' % (subject or '...')
        if username: heading = heading + '%s, ' % (username)
        heading += time
        heading += '\n\n'
        return heading

    def discussionSeparator(self,page):
        return '\n------------------------------------------------------------\n'

    def addPurpleNumbersTo(self,page,t):
        return add_purple_numbers_to(t,page)

    def inlineImage(self, page, id, path):
        return '\n\nimage: %s/%s\n' % (page.pageUrl(),path)

    def linkFile(self, page, id, path):
        return '\n\nfile: %s/%s\n' % (page.pageUrl(),path)


class AbstractHtmlPageType(AbstractPageType):
    """
    I am an abstract base class for zwiki page types which support HTML.

    Override me and define _id and _name to make a usable page type
    object. See __init__.py for more.
    """
    
    supportsHtml = yes

    def renderCitationsIn(self, page, t):
        inblock = 0
        blocklines = []
        blockend=0
        lines = string.split(t, '\n')
        t = ""
        for i in range(len(lines)):
            m = re.match(r'^>\s?(.*)$', lines[i])
            if(m):
                if(not inblock):
                    t += string.join(lines[blockend:i],'\n')
                    t += '\n<blockquote type="cite">\n\n'
                inblock = 1
                blocklines.append(m.group(1))
            elif(inblock):
                inblock = 0
                blockend=i
                t += self.renderCitationsIn(page,string.join(blocklines, '\n'))
                t += '\n\n</blockquote>\n'
                blocklines = []
        t += string.join(lines[blockend:], '\n')
        return t 

    def makeCommentHeading(self, page,
                           subject, username, time, 
                           message_id=None,in_reply_to=None):
        heading = '\n\n'
        if message_id:
            # use the message id for linking, but strip the <>
            # and leave it unquoted, browsers can handle it
            heading += '<a name="msg%s"></a>\n' % \
                       re.sub(r'^<(.*)>$',r'\1',message_id)
        if page.inCMF():
            heading += \
              '<img src="discussionitem_icon.gif" style="border:none; margin:0" />'
        heading += '<b>%s</b> --' % (subject or '...') #more robust
        if username: heading = heading + '%s, ' % (username)
        if message_id:
            heading += ' <a href="%s#msg%s">%s</a>' % \
                       (page.page_url(),
                        re.sub(r'^<(.*)>$',r'\1',message_id),
                        html_quote(time))
            inreplytobit = '&in_reply_to='+quote(message_id)
        else:
            heading += html_quote(time)
            inreplytobit = ''
        #heading += ( (' <a href="%s?subject=%s%s#bottom">' 
        #             % (page.page_url(),quote(subject or ''),inreplytobit)) +
        #             + _("reply") + '</a>' )
        
        heading += ' <a href="%s?subject=%s%s#bottom">reply</a>'\
                   % (page.page_url(),quote(subject or ''),inreplytobit)

                     
        heading += '<br />\n'
        return heading

    def discussionSeparator(self,page):
        # we want to customize the heading style in the stylesheet..
        # but also have it look ok by default in plone, which has it's own..
        # without preventing it being overridden - perhaps b outside the span
        # will work
        return '\n\n<a name="comments"><br /><b><span class="commentsheading">%(comments)s:</span></b></a>\n\n' % \
               { "comments":_("comments") }
            
    def inlineImage(self, page, id, path):
        return '\n\n<img src="%s" />\n' % path

    def linkFile(self, page, id, path):
        return '\n\n<a href="%s">%s</a>\n' % (path,id)
