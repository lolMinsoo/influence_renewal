import asyncio
import gspread 
from google.oauth2.service_account import Credentials 
import datetime
import discord 

from jshbot import data, configurations, plugins, utilities 
from jshbot.exceptions import ConfiguredBotException
from jshbot.commands import (
    Command, SubCommand, ArgTypes, Arg, Opt, Elevation, MessageTypes, Response)

__version__ = '0.2.0'
CBException = ConfiguredBotException('BDO Influence Renewal Plugin')
uses_configuration = True

###################################################################################################
###################################################################################################
### These are specific to a guild anyways, don't need to change the spreadsheet shit. #############
###################################################################################################
###################################################################################################


# SHEET NAMES
SPREADSHEET_NAME = ''
FORM_NAME = ''
MEMBER_LIST_NAME = ''
NW_ATTENDANCE_NAME = ''
NW_SUNDAY = 
NW_MONDAY = 

gc = None

# SHEET SPECIFIC
SHEET_TIMESTAMP = 
SHEET_FAMILY_NAME = 
SHEET_OFFICER_NAME = 
SHEET_DAILY_PAY_VALUE = 
###################################################################################################
###################################################################################################
### These are specific to a guild anyways, don't need to change the spreadsheet shit. #############
###################################################################################################
###################################################################################################

# credentials
@plugins.on_load
def init_gs_client(bot):
    global gc
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    config = configurations.get(bot, __name__)
    credentials = Credentials.from_service_account_info(config['credentials'], scopes=scope)
    gc = gspread.authorize(credentials)


async def check_whitelist(bot, context):
    config = configurations.get(bot, __name__)
    if config['use_whitelist'] and context.guild.id not in config['whitelist']:
        raise CBException('This server is not whitelisted to use this command.')


@plugins.command_spawner
def get_commands(bot):
    """Returns a list of commands associated with this plugin."""
    new_commands = []

    new_commands.append(Command(
        'sheet', subcommands=[
            SubCommand(
                Opt('new'),
                Arg('family_name'), 
                Arg('daily_pay_value', convert=int, check=lambda n, f, v, *a: 0 <= v <= 5000000,
                    check_error='Daily pay value must be between 0 and 5000000 inclusive.', 
                    argtype=ArgTypes.MERGED), 
                doc='Updates Google Sheet with a new 10k renewal.',
                function=update_to_sheet,
                elevated_level=Elevation.BOT_MODERATORS),
            SubCommand(
                Opt('kick'),
                Arg('family_name'),
                doc='Kicks a member from the spreadsheet.',
                function=kick_member,
                elevated_level=Elevation.GUILD_OWNERS),
            SubCommand(
                Opt('add'),
                Arg('family_name'),
                Arg('discord_name', argtype=ArgTypes.MERGED),
                doc='Adds a member to sheet',
                function=invite_member,
                elevated_level=Elevation.GUILD_OWNERS),
            SubCommand(
                Opt('attendance'),
                doc='Takes attendance in current channel',
                function=take_attendance,
                elevated_level=Elevation.GUILD_OWNERS)
        ],
        description='Updates from discord to google sheets because influence officers and '
                    'helpers are fucking lazy and can\'t update a fucking form.'
                    'Also Sean sucks Boba\'s hard throbbing chocolate fondue.',
        pre_check=check_whitelist, allow_direct=False))

    return new_commands

async def update_to_sheet(bot, context):
    """Updates family name to spreadsheet."""
    global gc
    family_name, daily_pay_value = context.arguments
    family_name = family_name.lower()
    author_id = context.author.id
    response = Response()

    # check family name for malicious character

    if not (len(family_name) > 1 and '=' not in family_name[0]):
        response.content = f'{family_name} is not a valid family name.'
        return response


    # VAR
    index_of_form = None
    next_index = 0
    index_of_member_list = None
    list_of_family_names = []

    # opens spreadsheet
    sh = await utilities.future(gc.open, SPREADSHEET_NAME)

    # gets all available worksheets
    worksheet = await utilities.future(sh.worksheets)

    # get the index of the form we want
    for i, sheet in enumerate(worksheet):
        if FORM_NAME in str(sheet):
            index_of_form = i
        if MEMBER_LIST_NAME in str(sheet):
            index_of_member_list = i
            
    # checks to see if one of these doesn't exist
    if ((index_of_form is None) or (index_of_member_list is None)):
        response.content = 'Something went wrong when initializing sheets.'
        return response

    # getting member list
    form_member_data = await utilities.future(sh.get_worksheet, index_of_member_list)
    form_member_list = await utilities.future(form_member_data.get_all_values)
    for i, row in enumerate(form_member_list):
        if i > 4:  # names start on row 4 here, first column
            if len(row[0]) != 0:
                list_of_family_names.append(row[0].lower())

    # open the form sheet
    form_data = await utilities.future(sh.get_worksheet, index_of_form)
    form_values = await utilities.future(form_data.get_all_values)
    form = await utilities.future(sh.get_worksheet, index_of_form)

    # iterate over rows till we find an empty index
    for i, row in enumerate(form_values):
        if len(row[0]) != 0:
            next_index = i

    next_index += 2  # this is the new empty row, +1 for next row and +1 because index starts at 1
    current_time = datetime.datetime.now().strftime('%m/%d/%Y %H:%M:%S')

    # fill the sheet
    await utilities.future(form.update_cell, next_index, SHEET_TIMESTAMP, current_time)                 # row 1
    await utilities.future(form.update_cell, next_index, SHEET_FAMILY_NAME, family_name)                # row 2
    await utilities.future(form.update_cell, next_index, SHEET_OFFICER_NAME, str(context.author))       # row 4
    await utilities.future(form.update_cell, next_index, SHEET_DAILY_PAY_VALUE, daily_pay_value)        # row 5
    response.content = f'<@{author_id}> renewed {family_name} on {current_time} with a daily pay value of {daily_pay_value}'

    # well fuck
    if family_name not in list_of_family_names:
        response.content += f', however, {family_name} does not exist. Check spreadsheet/ask officer for help.'
    
    form.sort((1, 'des'))

    return response

async def kick_member(bot, context): 
    """Deletes member from spreadsheet."""
    global gc
    family_name = context.arguments[0]
    family_name = family_name.lower()
    author_id = context.author.id
    response = Response()


    # VAR
    index_of_member_list = None
    list_of_family_names = []
    index_of_user = None

    # Check for malicious family name.
    if not (len(family_name) > 1 and '=' not in family_name[0]):
        response.content = f'{family_name} is not a valid family name.'
        return response

    # opens spreadsheet
    sh = await utilities.future(gc.open, SPREADSHEET_NAME)

    # gets all available worksheets
    worksheet = await utilities.future(sh.worksheets)

    # get index of member list
    for i, sheet in enumerate(worksheet):
        if MEMBER_LIST_NAME in str(sheet):
            index_of_member_list = i

    if index_of_member_list == None:
        response.content = 'Something went wrong when initalizing sheets (check member list name).'
        return response

    # get member list
    form_member_data = await utilities.future(sh.get_worksheet, index_of_member_list)
    form_member_list = await utilities.future(form_member_data.get_all_values)
    for i, row in enumerate(form_member_list):
        if i >= 4: # names start on row 4 here
            if len(row[0]) != 0:
                list_of_family_names.append(row[0].lower())

    # invalid family name
    if family_name not in list_of_family_names:
        response.content = f'{family_name} not a valid family name.'
        return response

    # get index of user
    index_of_user = list_of_family_names.index(family_name)
    index_of_user += 5 # offset, sheet specific

    # deletes entries in that row
    await utilities.future(form_member_data.update, f'A{index_of_user}:E{index_of_user}', [['', '', '', '', '']], value_input_option='user_entered')

    form_member_data.sort((1, 'asc'), range='A5:Z105')

    current_time = datetime.datetime.now().strftime('%m/%d/%Y %H:%M:%S')
    response.content = f'<@{author_id}> successfully kicked {family_name} on {current_time} from the spreadsheet.'
    return response

async def invite_member(bot, context): 
    """Adds member to spreadsheet."""
    global gc
    #family_name, discord_name = context.arguments
    family_name = context.arguments[0]
    family_name = family_name.lower()
    discord_name = context.arguments[1]
    author_id = context.author.id
    response = Response()
    
    # VAR
    index_of_member_list = None
    list_of_family_names = []
    index_of_user = None
    empty_index = 0

    # Check for malicious family name.
    if not (len(family_name) > 1 and '=' not in family_name[0]):
        response.content = f'{family_name} is not a valid family name.'
        return response

    if '=' == discord_name[0] or '#' not in discord_name:
        response.content = f'{discord_name} is not a valid Discord name. Cannot start with = or does not have a numeric identifier.'
        return response
   
    # opens spreadsheet
    sh = await utilities.future(gc.open, SPREADSHEET_NAME)

    # gets all available worksheets
    worksheet = await utilities.future(sh.worksheets)
   
    # get index of member list
    for i, sheet in enumerate(worksheet):
        if MEMBER_LIST_NAME in str(sheet):
            index_of_member_list = i

    if index_of_member_list == None:
        response.content = 'Something went wrong when initalizing sheets (check member list name).'
        return response

    # get member list
    form_member_data = await utilities.future(sh.get_worksheet, index_of_member_list)
    form_member_list = await utilities.future(form_member_data.get_all_values)
    for i, row in enumerate(form_member_list):
        if i >= 4: # names start on row 4 here
            if len(row[0]) != 0:
                list_of_family_names.append(row[0].lower())

    if family_name in list_of_family_names:
        response.content = f'{family_name} is already on the sheet!'
        return response
    
    for i, element in enumerate(form_member_list):
        if len(element[0]) > 1:
            empty_index = i
            print(element[0])
    print(empty_index)
    print(form_member_list[i])
    empty_index += 2 # index starts at 1 for sheets and +1 for offset

    if empty_index == 106:
        response.content = 'The guild is currently full!'
        return response

    current_time = datetime.datetime.now().strftime('%m/%d/%Y %H:%M:%S')
    current_date = datetime.datetime.now().strftime('%Y-%m-%d')

    # fill sheet
    await utilities.future(form_member_data.update_cell, empty_index, 1, family_name)
    await utilities.future(form_member_data.update_cell, empty_index, 2, discord_name)
    await utilities.future(form_member_data.update_cell, empty_index, 3, current_date)
    await utilities.future(form_member_data.update_cell, empty_index, 4, 'Apprentice')
    await utilities.future(form_member_data.update_cell, empty_index, 5, 'Active')

    form_member_data.sort((1, 'asc'), range='A5:Z105')

    response.content = f'<@{author_id}> successfully added {family_name} to sheet on {current_time}.'

    return response

async def take_attendance(bot, context):
    """Takes all users in voice channel and logs it."""
    response = Response()

    # VARS
    attendance_list = [] 
    day_of_week = None  # 0 = Monday, 6 = Sunday
    index_of_nw_attendance = None

    # checks to see if user is in voice channel
    if not context.author.voice:
       raise CBException('You must be in a voice channel to use this feature.')

    voice_channel = context.author.voice.channel

    # get all members within voice channel
    for member in voice_channel.members:
        attendance_list.append(member)

    if len(attendance_list) == 1:
        raise CBException('Are you really node warring with yourself? Loser.')

    # get day
    day_of_week = datetime.datetime.today().weekday()
    if day_of_week == 5:
        raise CBException('Since when did Influence siege? lmfao pvx guild btw')

    # opens spreadsheet + nw attendance
    sh = await utilities.future(gc.open, SPREADSHEET_NAME)
    worksheet = await utilities.future(sh.worksheets)

    # get index of nw attendance
    for i, sheet in enumerate(worksheet):
        if NW_ATTENDANCE_NAME in str(sheet):
            index_of_nw_attendance = i

    nw_attendance = await utilities.future(sh.get_worksheet, index_of_nw_attendance)


    # error handling
    if index_of_nw_attendance == None:
        response.content = 'Something went wrong when initializing sheets (check nw attendance name).'
        return response

    for index in range(len(attendance_list)):
        if day_of_week == 6:  # if sunday
            await utilities.future(nw_attendance.update_cell, 3+index, NW_SUNDAY, str(attendance_list[index]))
        else:
            await utilities.future(nw_attendance.update_cell, 3+index, NW_MONDAY+day_of_week, str(attendance_list[index]))

    response.content = 'Attendance successfully taken.'
    return response