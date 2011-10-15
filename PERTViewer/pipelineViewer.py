"""
    Web Application that is called from a Shotgun Tool Menu to create Redo Tasks

    The python script is an URL action script that is called from Shotgun.  Data
    from the current shotgun page is passed in the form of a post URL operation.
"""
__copyright__ = """
PERT Maker Software for Shotgun
Copyright 2011 Disney Enterprises, Inc.  All rights reserved

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

 * Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.

 * Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in
   the documentation and/or other materials provided with the
   distribution.

 * The names "Disney", "Walt Disney Pictures", "Walt Disney Animation
   Studios" or the names of its contributors may NOT be used to
   endorse or promote products derived from this software without
   specific prior written permission from Walt Disney Pictures.

Disclaimer: THIS SOFTWARE IS PROVIDED BY WALT DISNEY PICTURES AND
CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING,
BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE, NONINFRINGEMENT AND TITLE ARE DISCLAIMED.
IN NO EVENT SHALL WALT DISNEY PICTURES, THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND BASED ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.
"""
from mod_python import apache

import sys
import os
import tempfile
import traceback
import cgi
import logging.config
from datetime import datetime, timedelta #@UnresolvedImport
import pydot
import shotgun_api3 as shotgun

SERVER_PATH = '%%YOUR SHOTGUN SERVER%%'
SCRIPT_KEY = '%%YOUR SCRIPT KEY%%'
SCRIPT_NAME = '%%YOUR SCRIPT NAME %%'

HEADER_STR = """<<table BORDER="0" CELLBORDER="0" CELLSPACING="0">
                 <tr><TD ALIGN="CENTER" COLSPAN="2"><B>%s</B></TD></tr>
                 <tr><td ALIGN="LEFT" COLSPAN="2">LEGEND:</td></tr>
                 <tr>
                   <td VALIGN="TOP" ALIGN="LEFT">
                         Task States:<BR ALIGN="LEFT"/>
                         <FONT COLOR="#77cef3">Pre Inventory </FONT><BR ALIGN="LEFT"/>
                         <FONT COLOR="#f8f7d3">Inventory </FONT><BR ALIGN="LEFT"/>
                         <FONT COLOR="#66abff">In Work </FONT><BR ALIGN="LEFT"/>
                         <FONT COLOR="#99ff99">Approved </FONT><BR ALIGN="LEFT"/>
                         <FONT COLOR="#009100">Completed </FONT><BR ALIGN="LEFT"/>
                         <FONT COLOR="#e48c8e">Omitted </FONT>
                   </td>
                   <td VALIGN="TOP" ALIGN="RIGHT">
                     <table BORDER="0" CELLBORDER="0" CELLSPACING="0">
                       <tr>
                         <td VALIGN="TOP" ALIGN="LEFT">Date Field</td>
                         <td VALIGN="TOP" ALIGN="LEFT">State</td>
                       </tr>
                       <tr>
                         <td VALIGN="TOP" ALIGN="LEFT">left lower date</td>
                         <td VALIGN="TOP" ALIGN="LEFT">Inventory or Start Date <BR ALIGN="LEFT"/><FONT COLOR="#555555">gray</FONT> :pre inventory,  <FONT COLOR="red">red</FONT>: upstream dep broken</td>
                       </tr>
                       <tr>
                         <td ALIGN="LEFT">middle duration </td>
                         <td ALIGN="LEFT">Duration (days) </td>
                       </tr>
                       <tr>
                         <td ALIGN="left">right lower date </td>
                         <td VALIGN="TOP" ALIGN="LEFT">Completed Date<BR ALIGN="LEFT"/><FONT COLOR="green">green</FONT>: omitted/completed, <FONT COLOR="red">red</FONT>: downstream dep broken</td>
                       </tr>
                       <tr>
                         <td ALIGN="LEFT">one date </td>
                         <td VALIGN="TOP" ALIGN="LEFT">Milestone Date<BR ALIGN="LEFT"/><FONT COLOR="green">green</FONT>: omitted/completed, <FONT COLOR="red">red</FONT>: downstream dep broken</td> 
                       </tr>
                     </table>
                     </td>
                   </tr>
              </table>>"""

NODE_FMT_STR = '''<<TABLE BORDER="1" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4" >
                   <TR><TD COLSPAN="3" ALIGN="CENTER"><FONT color="%s">%s</FONT></TD></TR> 
                   <TR><TD COLSPAN="3" ALIGN="CENTER"><FONT color="%s">%s</FONT></TD></TR>
                   <TR><TD ALIGN="LEFT">%s</TD>
                       <TD ALIGN="CENTER">%s</TD>
                       <TD ALIGN="RIGHT">%s</TD></TR>
                    </TABLE>>'''
MILESTONE_FMT_STR = '''<<TABLE BORDER="1" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4"> 
                       <TR><TD COLSPAN="3" ALIGN="CENTER"><FONT color="%s">%s</FONT></TD></TR> 
                       <TR><TD COLSPAN="3" ALIGN="CENTER"><FONT color="%s">%s</FONT></TD></TR>
                       <TR><TD COLSPAN="3" ALIGN="CENTER">%s</TD></TR>
                      </TABLE>>'''

NODE_CREDIT_FMT_STR = '''<<TABLE BORDER="1" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4" >
                   <TR><TD COLSPAN="3" ALIGN="CENTER"><FONT color="%s">%s</FONT></TD></TR> 
                   <TR><TD COLSPAN="3" ALIGN="CENTER"><FONT color="%s">%s</FONT></TD></TR>
                   <TR><TD COLSPAN="3" ALIGN="CENTER">%s</TD></TR>
                   <TR><TD ALIGN="LEFT">%s</TD>
                       <TD ALIGN="CENTER">%s</TD>
                       <TD ALIGN="RIGHT">%s</TD></TR>
                    </TABLE>>'''
MILESTONE_CREDIT_FMT_STR = '''<<TABLE BORDER="1" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4"> 
                       <TR><TD COLSPAN="3" ALIGN="CENTER"><FONT color="%s">%s</FONT></TD></TR> 
                       <TR><TD COLSPAN="3" ALIGN="CENTER"><FONT color="%s">%s</FONT></TD></TR>
                       <TR><TD COLSPAN="3" ALIGN="CENTER">%s</TD></TR>
                       <TR><TD COLSPAN="3" ALIGN="CENTER">%s</TD></TR>
                      </TABLE>>'''

class ShotgunActionException( Exception ):
    '''
         Generic ShotgunAction Exception Class
    '''
    pass

logger = None
try:
    logging.config.fileConfig( "/share/logs/prodman/prodman.conf", disable_existing_loggers=False)
    logger = logging.getLogger( "prodman.pipelineViewer" )
except IOError, e:
    logger = logging.getLogger() # Get the root logger

system_excepthook = sys.excepthook

def excepthook(exctype, value, traceBack):
    ''' Exception Trap Processing

    Grab Exceptions, report them to the log and email the support list
    '''
    if issubclass(exctype, StandardError):
        # figure out the current dpix version number
        version = "unknown version"
        try:
            import prodman.version
            version = prodman.version.version()
        except: # pylint: disable = W0702
            version = "1.0"
        # Send out an email with the traceback
        logger.exception("edisync [%s]: caught unhandled %s exception", version)
    return system_excepthook(exctype, value, traceBack)

sys.excepthook = excepthook

def _getStateInfo(state):
    ''' Return a Graph Color and State String for task state '''
    status = ""
    if state == 'omt':
        status =  'Omitted'
        statusColor = "#e48c8f"
    elif state == 'apr':
        status = 'Approved'
        statusColor = '#99ff99'
    elif state == 'cmpt':
        status = 'Completed'
        statusColor = "#009100"
    elif state == 'wrk':
        status = 'Active'
        statusColor = "#66aaff"
    elif state == 'inv':
        status = 'Inventory'
        statusColor = "#f8f7d3"
    else:
        status = 'Pre Inventory'
        statusColor  = "#77ccf3"
    return statusColor, status

def _getTitleCredits(task):
    ''' Return title, Credit Info '''
    title = cgi.escape(task['content'] or 'No Name')
    subDetail = ""
    if task['sg_element']:
        subDetail += task['sg_element']['name']
        title += '<BR ALIGN="CENTER"/>' + cgi.escape(subDetail)
    stepColor = None
    if task['step.Step.color']:
        colorR, colorG, colorB = task['step.Step.color'].split(',')
        stepColor = '#%02x%02x%02x' % (int(colorR), int(colorG), int(colorB))
    if not stepColor:
        stepColor = "black"
    taskCredits = ''
    if task['task_assignees']:
        for assignee in task['task_assignees']:
            if taskCredits:
                taskCredits += '<BR ALIGN="LEFT"/>'
            taskCredits += cgi.escape(assignee['name'])
    return title, stepColor, taskCredits

def _makeNode(task, taskMap): #pylint: disable = R0912
    '''' Create a Node for the task '''
    nodeAttrs = {'shape':'plaintext'}
    statusColor, status = _getStateInfo(task['sg_status_list'])
    title, stepColor, taskCredits = _getTitleCredits(task)
    startStr = ' &nbsp; '
    durStr = ' &nbsp; '
    endStr = ' &nbsp; '
    if not task['milestone'] and task['start_date'] and task['sg_status_list'] != 'omt':
        font = None
        if task['dependency_violation']:
            font = 'red'
        if task['sg_status_list'] ==  'wrk':
            font = '#66abff'
        elif task['sg_status_list'] == 'pre':
            font = '#555555'
        if font:
            startStr = '<FONT COLOR="' + font + '">'
        else:
            startStr = ''
        startStr += task['start_date']
        if font:
            startStr += '</FONT>'
    if task['duration'] and not task['milestone']:
        durStr = '%d' % (task['duration'] / (9*60))
    if task['due_date']:
        font = None
        if task['milestone'] and task['dependency_violation']:
            font = 'red'
        elif _getTaskDepError(task, taskMap):
            font = 'red'
        elif task['sg_status_list'] in ['omt', 'cmpt']:
            font = 'green'
        if font:
            endStr = '<FONT COLOR="' + font + '">'
        else:
            endStr = ''
        endStr += task['due_date']
        if font:
            endStr += '</FONT>'
    if task['milestone']:
        if taskCredits:
            nodeAttrs['label'] = MILESTONE_CREDIT_FMT_STR % ( stepColor, title, 
                                                       statusColor, status, taskCredits, endStr)
        else:
            nodeAttrs['label'] = MILESTONE_FMT_STR % ( stepColor, title, 
                                                       statusColor, status, endStr)
    elif taskCredits:
        nodeAttrs['label'] = NODE_CREDIT_FMT_STR % ( stepColor, title, statusColor, 
                                                     status,  taskCredits, startStr, durStr,endStr)
    else:
        nodeAttrs['label'] = NODE_FMT_STR % ( stepColor, title, statusColor, 
                                              status, startStr, durStr, endStr)
    nodeName = 'Task%d' % task['id']
    return pydot.Node(nodeName, **nodeAttrs) #pylint: disable=W0142

def _getTaskDepError(task, taskMap):
    ''' Return True if task end date is before any of its downstream tasks '''
    if not task['downstream_tasks'] or not task['due_date']:
        return False
    for depTask in task['downstream_tasks']:
        dep = taskMap.get(depTask['id'])
        if dep and dep['start_date']:
            offset = task['depmap'].get(dep['id']) or 0
            if _ifDateBefore(dep['start_date'], task['due_date'], offset):
                return True
    return False

def draw_pipeline(server, idFilter): #pylint: disable = R0912
    ''' Draw Pipeline Image and return '''
    sg = shotgun.Shotgun( server, SCRIPT_NAME, SCRIPT_KEY )
    sgFilter =  {
                 "logical_operator": "and",
                 "conditions": [
                                {
                                 "logical_operator": "or",
                                 "conditions": idFilter
                                 }
                                ]
                 }

    tasks = sg.find('Task', sgFilter,
                    ['content', 'downstream_tasks', 'milestone', 'sg_status_list', 'pinned',
                     'dependency_violation',  'sg_element', 'start_date', 'due_date', 
                     'task_assignees', 'inventory_date', 'duration', 'step.Step.color', 'entity', 
                     'task_template' ])
    
    taskMap = {}
    pageTitle = None
    for task in tasks:
        if not pageTitle:
            if task['entity']:
                pageTitle = 'PERT Graph for %s:%s' % (task['entity']['type'], 
                                                      task['entity']['name'])
            elif task['task_template']:
                pageTitle = 'PERT Graph for Task Template:%s' % (task['task_template']['name'])
        taskMap[task['id']] = task
    
    title = HEADER_STR.replace('%s', cgi.escape(pageTitle or 'PERT Graph'))
    graph = pydot.Dot('Pipeline', graph_type = 'digraph', simplify=True, bgcolor='white',
                      labeljust='l', labelloc='tl', label=title)

    for task in tasks:
        if task['downstream_tasks']:
            depMap = {}
            for dep in task['downstream_tasks']:
                dp = taskMap.get(dep['id'])
                if not dp:
                    dp = sg.find_one('Task', 
                                     [['id', 'is', dep['id']]],
                                     ['content', 'downstream_tasks', 'milestone', 'sg_status_list',
                                      'sg_element', 'start_date', 'due_date', 'inventory_date',
                                      'task_assignees', 'duration', 'step.Step.color', 'pinned', 
                                      'dependency_violation', 'entity', 'task_template' ])
                    taskMap[dp['id']] = dp
                    tasks.append(dp)
                if dp:
                    dep = sg.find_one('TaskDependency', 
                                      [['task', 'is', {'type':'Task', 'id':dp['id']}],
                                       ['dependent_task', 'is', {'type':'Task', 'id': task['id']}]],
                                       ['offset_days'])
                    depMap[dp['id']] = dep['offset_days']
            task['depmap'] = depMap

    for task in tasks:
        node = _makeNode(task, taskMap)
        graph.add_node(node)
        task['node'] = node
    for task in tasks:
        if task['downstream_tasks']:
            for dep in task['downstream_tasks']:
                dp = taskMap.get(dep['id'])
                if dp:
                    offset = task['depmap'].get(dp['id']) or 0
                    linecolor = "red" if _ifDateBefore(dp['start_date'], task['due_date'], offset) \
                            else 'black'
                    if offset:
                        edge = pydot.Edge(task['node'], dp['node'], label="%d" % offset,
                                          fontcolor='blue', color = linecolor)
                    else:
                        edge = pydot.Edge(task['node'], dp['node'], color = linecolor)
                graph.add_edge(edge)

    tf = tempfile.mkstemp()
    os.close(tf[0])
    graph.write_gif(tf[1]) #pylint: disable=E1101
    image = open(tf[1],'r').read()
    os.unlink(tf[1])
    return image

def _ifDateBefore(start, end, offset):
    ''' return if start+offset > end '''
    if not start or not end:
        return False
    startdate = datetime.strptime(start, '%Y-%m-%d').date()
    tmpdate = datetime.strptime(end, '%Y-%m-%d')
    enddate = tmpdate.date()
    delta = timedelta(days=(-1 if (offset or 0) < 0 else 1))
    for dummy_count in range(0, abs(offset or 0)):
        enddate += delta
        while enddate.weekday() in [5, 6]:
            enddate += delta
    return startdate.strftime('%Y%m%d') < enddate.strftime('%Y%m%d')

def _convert_ids_to_filter( ids ):
    ''' Convert the lists of ids into a shotgun filter list '''
    sgFilter = [{'path': 'id', 'relation': 'is', 'values': [int( itemId )]} for itemId in ids ]
    return sgFilter

# ----------------------------------------------
# Main Block
# ----------------------------------------------
def view( req ):
    '''
    URL action to create Redo Tasks
    '''
    logger.info( 'Pipeline View Request Started' )
    try:
        sids = None
        ids_filter = None
        params = req.form

        if 'selected_ids' in params and params['selected_ids']:
            sids = params['selected_ids'].split(',')
        elif 'ids' in params and params['ids']:
            sids = params['ids'].split(',')

        if sids:
            selected_ids = [int( itemId ) for itemId in sids]
            ids_filter = _convert_ids_to_filter( selected_ids )
    
            shotgunServer = 'server_hostname' in params and  \
                    'http://' + params['server_hostname'] or \
                    'http://shotgun.fas.fa.disney.com'
            logger.debug("server returned: %s" % shotgunServer)
            image = draw_pipeline(shotgunServer, ids_filter)
            req.content_type = 'image/gif'
            req.send_http_header()
            req.write( image )
    except Exception:  #pylint: disable=W0703
        logger.exception( 'Error Handling View Request' )
        fd = open('/tmp/error.txt','a')
        traceback.print_exc(file=fd)
        fd.close()

    logger.info( "Pipeline View Request finished." )
    return apache.OK
            
