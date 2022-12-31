from aenum import NamedTuple
from openerp import SUPERUSER_ID
from openerplib import AttrDict
import email
import logging
import smtplib
import socket
import time

_logger = logging.getLogger(__name__)

class MergeSelected(object):
    """
    Support merging user-selected records
    """

    def get_relations(self, cr, uid, oe_rel, context=None):
        """
        get tables that link to TABLE and that TABLE links to via _id fields

        upstream  -->   self.table  --> downstream
        inherits  --^
        ( res.user      res.partner                )
        ( sample.memo                  res.country )

        `downstream` are tables pointed to by `self`'s fields
        `upstream` are tables that point to `self`
        `inheriting` are any `upstream` tables that form a logical record with `self`, and
                     should not be updated to point to winning record
        """
        table = self._name
        ir_model_fields = self.pool.get('ir.model.fields')
        upstream = [
                oe_rel(r['model'], r['name'])
                for r in ir_model_fields.read(
                    cr, uid,
                    [('relation','=',table)],
                    fields=['model','name'],
                    )]
        downstream = [
                oe_rel(r['relation'], r['name'])
                for r in ir_model_fields.read(
                    cr, uid,
                    [('model','=',table),('relation','!=','')],
                    fields=['relation','name'],
                    )]
        # inheriting lists any tables in `upstream` that logically create a record with `table`
        # inheriting tables are removed from upstream
        inheriting = set()
        for rel in upstream:
            model = self.pool.get(rel.model)
            if model is None:
                continue
            for table_name, field in model._inherits:
                if table_name == table:
                    inh_rel = oe_rel(rel.model, field)
                    if inh_rel in upstream:
                        inheriting.add(inh_rel)
        upstream = list(set(upstream) - inheriting)
        return upstream, downstream, inheriting

    def merge(self, cr, uid, ids, prefer=[], context=None):
        """
        Combine multiple records into one, substituting the one where ever the removed records were.

        `prefer` is a list of fields to use as tie-breakers, where not empty is better than empty.
        """
        context = context or {}
        context['maintenance'] = True
        inheriting_fields = [v for k,v in self._inherits]
        fields = inheriting_fields + prefer
        oe_rec_fields = inheriting_fields + prefer + [
                'model', 'id', 'xmlid', 'tertiary',
                'create_uid', 'create_date', 'write_uid', 'write_date',
                ]
        if 'xml_id' in self._columns:
            fields.insert(0, 'xml_id')
            oe_rec_fields.insert(0, 'xml_id')
        OERec = NamedTuple('OERec', oe_rec_fields)
        OERel = NamedTuple('OERel', ['model', 'field'])
        upstream, downstream, inherited = self.get_relations(cr, SUPERUSER_ID, OERel, context=context)
        # records = get_main_records(main_model, domain, dupe, tuple(inheriting_fields), use_empty)
        records = self.read(cr, SUPERUSER_ID, ids, fields=fields, context=context)
        # add the metadata
        meta = dict(
                (r['id'], r)
                for r in self.meta_read(cr, SUPERUSER_ID, ids, details=True, context=context)
                )
        for i, rec in enumerate(records):
            rec.update(meta[rec['id']])
            records[i] = OERec(model=self._name, tertiary={}, **rec)
        records = self.get_tertiary_ids(cr, SUPERUSER_ID, records, upstream, context=context)
        primary, secondary = self.pick_one(records, prefer)
        error = False
        for rec in secondary:
            for rel, ids in rec.tertiary.items():
                model = self.pool.get(rel.model)
                try:
                    model.write(cr, SUPERUSER_ID, ids, {rel.field: primary.id}, context=context)
                except Exception:
                    _logger.exception('an error occurred')
                    raise
                else:
                    self.unlink(cr, SUPERUSER_ID, [rec.id], context=context)
        return not error

    def get_tertiary_ids(self, cr, uid, records, upstream, context=None):
        # records = [OERec, OERec, ...]
        kept_records = []
        relations = set()
        for rec in records:
            for rel in upstream:
                u_table = self.pool.get(rel.model)
                if u_table is None:
                    # non-existent table
                    continue
                if not u_table._auto:
                    # abstract table
                    continue
                if (
                        rel.field not in u_table._all_columns
                        # or rel.field in u_table._x2many_fields
                        or u_table._columns[rel.field]._type in ('one2many','many2many')
                        or not self.is_searchable(cr, uid, rel.model, rel.field, context=context)
                    ):
                    continue
                u_records = u_table.read(
                        cr, SUPERUSER_ID,
                        [(rel.field,'=',rec.id)],
                        fields=[rel.field],
                        context=None,
                        )
                if not u_records:
                    continue
                u_ids = [t['id'] for t in u_records] 
                if u_ids:
                    rec.tertiary[rel] = u_ids
                    relations.add(rel)
            kept_records.append(rec)
        return kept_records

    def is_searchable(self, cr, uid, table, field, context=None):
        desc = self.pool.get('ir.model.fields').read(cr, uid, [('model','=',table),('name','=',field)], fields=['selectable'], context=context)
        return desc[0]['selectable']

    def pick_one(self, records, prefer):
        # given a group of records picks the one:
        # - with an xmlid in the fis namespace
        # - created by fis
        # - created by admin
        # - created earliest
        #
        # records = [OERec, OERec, ...]
        if len(records) < 2:
            abort('only one record!!')
        def key(record):
            # { rel1: ids1, res2: ids2, ...}
            count = 0
            for ids in record.tertiary.values():
                count += len(ids)
            if record.xmlid and record.xmlid.startswith(('fis.','whc.')):
                is_fis = 1  # 1 means yes (sorts after 0)
            else:
                is_fis = 0  # 0 means no (sorts before 1)
            preferred = sum([1 for p in prefer if getattr(record, p, None)])
            return -is_fis, -preferred, -count, record.create_date
        records.sort(key=lambda r: key(r))
        primary = records.pop(0)
        return primary, records


class Normalize(object):
    """Adds support for normalizing character fields.

    `create` and `write` both strip leading and trailing white space, while
    `check_unique` does a case-insensitive compare."""

    def check_unique(self, field, cr, uid, ids, context=None):
        """Case insensitive compare.

        Meant to be called as:

            lambda *a: self.check_unique(<field>, *a)

        """
        existing_ids = self.search(cr, 1, [], context=context)
        values = set([r[field].lower() for r in self.browse(cr, uid, existing_ids, context=context) if r.id not in ids])
        for new_rec in self.browse(cr, uid, ids, context=context):
            if new_rec[field].lower() in values:
                return False
        return True

    def create(self, cr, uid, vals, context=None):
        strip_whitespace(vals)
        return super(Normalize, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        strip_whitespace(vals)
        return super(Normalize, self).write(cr, uid, ids, vals, context=context)


def check_company_settings(obj, cr, uid, *args):
    company = obj.pool.get('res.company')
    company = company.browse(cr, uid, company.search(cr, uid, [(1,'=',1)]))[0]
    values = {}
    if isinstance(args[0][0], tuple):
        all_args = args
    else:
        all_args = (args, )
    for args in all_args:
        for setting, error_name, error_msg in args:
            values[setting] = company[setting]
            if not values[setting]:
                raise ValueError(error_msg % error_name)
    return values

def get_user_login(obj, cr, uid, user_ids, context=None):
    res_users = obj.pool.get('res.users')
    if isinstance(user_ids, (int, long)):
        record = res_users.browse(cr, uid, user_ids, context=context)
        return record.login
    res = {}
    records = res_users.browes(cr, uid, user_ids, context=context)
    for record in records:
        res[record.id] = record.login
    return res

def get_user_timezone(obj, cr, uid, user_ids=None, context=None):
    if not user_ids:
        user_ids = [uid]
    result = {}
    res_users = obj.pool.get('res.users')
    users = res_users.browse(cr, uid, user_ids, context=context)
    for user in users:
        result[user.id] = user.tz or 'UTC'
    return result

def mail(oe, cr, uid, message):
    """
    sends email.message to server:port
    """
    if isinstance(message, basestring):
        message = email.message_from_string(message)
    # add UTC date header as OpenERP server is running in UTC time
    message['Date'] = \
            email.utils.formatdate(
                email.utils.mktime_tz(
                    time.localtime() + (0,)
                    ))
    targets = message.get_all('To', []) + message.get_all('Cc', []) + message.get_all('Bcc', [])
    original_sender = sender = message.get('From')
    ir_mail_server = oe.pool.get('ir.mail_server')
    errs = {}
    for rec in ir_mail_server.browse(cr, uid):
        server = port = None
        if not rec.active:
            continue
        server = rec.smtp_host
        port = rec.smtp_port
        if server and port:
            try:
                smtp = smtplib.SMTP(server, port)
            except socket.error, exc:
                send_errs = {}
                for rec in targets:
                    send_errs[rec] = (server, exc.args)
            else:
                try:
                    if original_sender is None:
                        sender = 'OpenERP <no-reply@%s>' % server
                        message['From'] = sender
                    send_errs = smtp.sendmail(sender, targets, message.as_string())
                    break
                except smtplib.SMTPRecipientsRefused, exc:
                    send_errs = {}
                    for user, detail in exc.recipients.items():
                        send_errs[user] = (server, detail)
                finally:
                    smtp.quit()
    else:
        # never found a good server, or was unable to send mail
        if original_sender is None:
            message['From'] = sender = 'OpenERP <no-reply@nowhere.invalid>'
        for user in send_errs or targets:
            try:
                server = 'mail.' + user.split('@')[1].strip('>')
                smtp = smtplib.SMTP(server, 25)
            except socket.error, exc:
                errs[user] = [send_errs and send_errs[user] or None, (server, exc.args)]
            else:
                try:
                    smtp.sendmail(sender, [user], message.as_string())
                except smtplib.SMTPRecipientsRefused, exc:
                    errs[user] = [send_errs and send_errs[user] or None, (server, exc.recipients[user])]
                finally:
                    smtp.quit()
    for user, errors in errs.items():
        for server, (code, response) in errors:
            _logger.warning('Error sending email -- %s: %s --> %s: %s' % (server, user, code, response))

def strip_whitespace(fields):
    """Strips whitespace from all str values in fields"""
    for fld, value in fields.items():
        if isinstance(value, (str, unicode)):
            fields[fld] = value.strip()

def Proposed(obj, cr, values, record=None, context=None):
    fields = obj._columns.keys()
    if record is None:
        record = AttrDict(fields)
        record.update(obj.default_get(cr, SUPERUSER_ID, fields, context=context))
        record.id = None
    else:
        old_rec, record = record, AttrDict()
        for f in fields:
            try:
                record[f] = old_rec[f]
            except KeyError:
                _logger.error('fields in old_rec: %r', old_rec._fields)
                raise
        record.id = old_rec['id']
    for key, value in values.items():
        column = obj._columns[key]
        if column._type not in ('many2one', 'one2many', 'many2many') or column.__class__.__name__ == 'function':
            record[key] = value
        else:
            if value is False:
                record[key] = ((), False)[column._type == 'many2one']
            else:
                field_table = obj.pool.get(column._obj)
                if column._type == 'many2one':
                    record[key] = field_table.browse(cr, SUPERUSER_ID, value, context=context)
                else:
                    # get current records into Proposed format
                    many_records = record[key] or []
                    many_records = [Proposed(field_table, cr, {}, r, context=context) for r in many_records]
                    # and update from values
                    for command in value:
                        cmd = command[0]
                        if cmd == 0:
                            # create
                            sub_values = command[2]
                            many_records.append(Proposed(field_table, cr, sub_values, context=context))
                        elif cmd == 1:
                            # update record
                            r_id, sub_values = command[1:]
                            for i, sub_record in enumerate(many_records):
                                if sub_record.id == r_id:
                                    many_records[i] = Proposed(field_table, cr, sub_values, sub_record, context=context)
                        elif cmd == 2 or cmd == 3:
                            # remove relationship (both) and delete target (2 only)
                            r_id = command[1]
                            many_records = [r for r in many_records if r.id != r_id]
                        elif cmd == 4:
                            # add relationship to existing target
                            r_id = command[1]
                            many_records.append(
                                Proposed(
                                    field_table, cr, {},
                                    field_table.browse(cr, SUPERUSER_ID, r_id, context=context),
                                    context=context,
                                    ))
                        elif cmd == 5:
                            many_records = []
                        elif cmd == 6:
                            # replace any existing links with these links
                            ids = command[2]
                            many_records = [
                                Proposed(field_table, cr, {}, r, context=context)
                                for r in field_table.browse(cr, SUPERUSER_ID, ids, context=context)
                                ]
                    record[key] = many_records
    return record

dynamic_page_stub = """\
<HTML>
  <HEAD>
    <script type="text/javascript">
    <!--
/**********************************************************************************
* Base on code from
*
* Dynamic Ajax Content- (c) Dynamic Drive DHTML code library (www.dynamicdrive.com)
* This notice MUST stay intact for legal use
* Visit Dynamic Drive at http://www.dynamicdrive.com/ for full source code
**********************************************************************************/


var bustcachevar = 1 /* bust potential caching of external pages after initial request? (1=yes, 0=no) */
var loadedobjects = ""
var rootdomain = "http://"+window.location.hostname
var bustcacheparameter = ""

function ajaxpage(url, containerid)
    {
    var xmlhttp = false;
    if (window.XMLHttpRequest) /*  IE7+, Firefox, Chrome, Opera, Safari */
        xmlhttp = new XMLHttpRequest();
    else if (window.ActiveXObject) {
        try {
            page_request = new ActiveXOjbect("Msxml2.XMLHTTP");
            }
        catch(e) {
            try {
                page_request = new ActiveXObject("Microsoft.XMLHTTP");
                }
            catch(e) {
                return false;
                }
            }
        }
    else
        return false;
    xmlhttp.onreadystatechange = function()
        {
        if (xmlhttp.readyState == 4 && xmlhttp.status == 200)
            loadpage(xmlhttp, containerid);
        }
    if (bustcachevar) /* if bust caching of external page */
        bustcacheparameter = (url.indexOf("?")!=-1) ? "&"+new Date().getTime() : "?"+new Date().getTime();
    xmlhttp.open('GET', url+bustcacheparameter, true);
    xmlhttp.send();
    }

function loadpage(xmlhttp, containerid)
    {
    /* if (xmlhttp.readyState == 4 && (xmlhttp.status==200 || window.location.href.indexOf("http")==-1)) */
    /* alert("alerting..."+xmlhttp+"...alerted") */
    /* ... */
    /* look for all containers with target id as I have not figured out how to get OE framework to clear */
    /* previous document, so I end up with multiple containers with the same containerid                 */
    var containers = document.querySelectorAll('[id=salesinqcontent]');
    var last = containers.length - 1;
    var target_div = containers[last];
    target_div.innerHTML = xmlhttp.responseText
    }

function loadobjs()
    {
    if (!document.getElementById)
        return;
    for (i=0; i<arguments.length; i++)
        {
        var file = arguments[i];
        var fileref = "";
        if (loadedobjects.indexOf(file) == -1) /* Check to see if this object has not already been added to page before proceeding */
            {
            if (file.indexOf(".js") != -1) /* If object is a js file */
                {
                fileref = document.createElement('script');
                fileref.setAttribute("type","text/javascript");
                fileref.setAttribute("src", file);
                }
            else if (file.indexOf(".css") != -1) /* If object is a css file */
                {
                fileref = document.createElement("link");
                fileref.setAttribute("rel", "stylesheet");
                fileref.setAttribute("type", "text/css");
                fileref.setAttribute("href", file);
                }
            }
        if (fileref != "")
            {
            document.getElementsByTagName("head").item(0).appendChild(fileref);
            loadedobjects += file + " "; /* Remember this object as being already added to page */
            }
        }
    }
    // -->
    </script>
  </HEAD>
  <BODY>
      %s
  </BODY>
</HTML>
"""

static_page_stub = """\
<HTML>
  <HEAD>
  </HEAD>
  <BODY>
      %s
  </BODY>
</HTML>
"""
