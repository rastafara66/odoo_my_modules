# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import ldap, ldap.modlist
import logging
from odoo.addons.auth_signup.models.res_users import SignupError


_logger = logging.getLogger(__name__)

class resUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def signup(self, values, token=None):
        """ signup a user, to either:
            - create a new user (no token), or
            - create a user for a partner (with token, but no user for partner), or
            - change the password of a user (with token, and existing user).
            :param values: a dictionary with field values that are written on user
            :param token: signup token (optional)
            :return: (dbname, login, password) for the signed up user
        """
        password = values.get('password')
        values['password'] = ''

        db, login, p = super(resUsers, self).signup(values, token)
#        login = '%s@svami.in.ua' % login
        values['login'] = login
        self.create_entry(values, password, token)
        return db, login, password

    def create_entry(self, values, password, token=None):
        Ldap = self.env['res.company.ldap']
        for conf in Ldap.get_ldap_dicts():

            uid = values['login']
            dn = "uid=%s,%s" % (uid, conf['ldap_base'])
            if token:
                modlist = ldap.modlist.modifyModlist(
                    {'userPassword': '', },
                    {'userPassword': str(password), },
                )
            else:
                name = values.get('name')
                names = name.split(' ') if name  else []
                modlist = ldap.modlist.addModlist({
                    'objectClass': str('inetOrgPerson'),
                    'uid': str(uid),
                    'givenName': str(names[0]),
                    'sn': str(names[-1]),
                    'cn': str(name),
                    'description': str('svami.in.ua self reg'),
                    'userPassword': str(password),
                })

            try:

                conn = Ldap.connect(conf)
                ldap_password = conf['ldap_password'] or ''
                ldap_binddn = conf['ldap_binddn'] or ''
                conn.simple_bind_s(ldap_binddn.encode('utf-8'), ldap_password.encode('utf-8'))
                #                results = conn.search_st(conf['ldap_base'].encode('utf-8'), ldap.SCOPE_SUBTREE, filter,
                #                                        retrieve_attributes, timeout=60)
                if token:
                    conn.modify_s(dn, modlist)
                else:
                    conn.add_s(dn, modlist)
                conn.unbind()
            except ldap.INVALID_CREDENTIALS:
                _logger.error('LDAP bind failed.')
                raise
            except ldap.ALREADY_EXISTS:
                _logger.error('User Exists.')
                raise SignupError()
            except ldap.LDAPError, e:
                _logger.error('An LDAP exception occurred: %s', e)
                raise

            return

