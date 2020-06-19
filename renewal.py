import asyncio
import gspread 
from google.oauth2.service_account import Credentials 
import datetime
import discord 

from jshbot import data, configurations, plugins, utilities 
from jshbot.exceptions import ConfiguredBotException
from jshbot.commands import (
    Command, SubCommand, ArgTypes, Arg, Opt, Elevation, MessageTypes, Response)

__version__ = '0.1.0'
CBException = ConfiguredBotException('BDO Influence Renewal Plugin')
uses_configuration = True

###################################################################################################
###################################################################################################
### These are specific to a guild anyways, don't need to change the spreadsheet shit. #############
###################################################################################################
###################################################################################################


# SHEET NAMES
SPREADSHEET_NAME = ''  				# Name of the spreadsheet itself
FORM_NAME = ''						# Name of the renewal form
MEMBER_LIST_NAME = ''				# Name of the member list form

gc = None

# SHEET SPECIFIC
SHEET_TIMESTAMP = 1			# These are rows for the form.
SHEET_FAMILY_NAME = 2  
SHEET_OFFICER_NAME = 4
SHEET_DAILY_PAY_VALUE = 5

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
        'renew', subcommands=[
            SubCommand(
                Opt('new'),
                Arg('family_name'), 
                Arg('daily_pay_value', convert=int, check=lambda n, f, v, *a: 7000 <= v <= 5000000,
                    check_error='Daily pay value must be between 7000 and 5000000 inclusive.', 
                    argtype=ArgTypes.MERGED), 
                doc='Updates Google Sheet with a new 10k renewal.',
                function=update_to_sheet,
                elevated_level=Elevation.BOT_MODERATORS)
        ],
        description='Updates from discord to google sheets because influence officers and '
                    'helpers are fucking lazy and can\'t update a fucking form.',
        pre_check=check_whitelist, allow_direct=False))

    return new_commands

async def update_to_sheet(bot, context):
    """Updates family name to spreadsheet."""
    global gc
    family_name, daily_pay_value = context.arguments
    family_name = family_name.lower()
    author_id = context.author.id
    response = Response()

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

    return response

