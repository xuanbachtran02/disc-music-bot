import os
import re
import random
import hikari
import logging
import lavalink
import lightbulb
from googleapiclient.discovery import build

from bot.library.SpotifyClient import SpotifyClient
from bot.library.MusicClient import MusicClient

plugin = lightbulb.Plugin("Music", "🎧 Music commands")

url_rx = re.compile(r'https?://(?:www\.)?.+')

class EventHandler:
    """Events from the Lavalink server"""
    
    @lavalink.listener(lavalink.TrackStartEvent)
    async def track_start(self, event: lavalink.TrackStartEvent):

        player = plugin.bot.d.lavalink.player_manager.get(event.player.guild_id)
        
        await plugin.bot.update_presence(
            activity = hikari.Activity(
            name = f"{player.current.author} - {player.current.title}",
            type = hikari.ActivityType.LISTENING
        ))

        logging.info("Track started on guild: %s", event.player.guild_id)

    @lavalink.listener(lavalink.TrackEndEvent)
    async def track_end(self, event: lavalink.TrackEndEvent):

        player = plugin.bot.d.lavalink.player_manager.get(event.player.guild_id)

        if not player.queue:
            await plugin.bot.update_presence(
                activity = hikari.Activity(
                    name=f"/play",
                    type=hikari.ActivityType.LISTENING
                ))

        logging.info("Track finished on guild: %s", event.player.guild_id)

    @lavalink.listener(lavalink.TrackExceptionEvent)
    async def track_exception(self, event: lavalink.TrackExceptionEvent):
        logging.warning("Track exception event happened on guild: %d", event.player.guild_id)

    @lavalink.listener(lavalink.QueueEndEvent)
    async def queue_finish(self, event: lavalink.QueueEndEvent):
        pass

# on ready, connect to lavalink server
@plugin.listener(hikari.ShardReadyEvent)
async def start_lavalink(event: hikari.ShardReadyEvent) -> None:

    client = lavalink.Client(plugin.bot.get_me().id)

    client.add_node(
        host='localhost',
        port=int(os.environ['LAVALINK_PORT']),
        password=os.environ['LAVALINK_PASS'],
        region='us',
        name='default-node'
    )

    client.add_event_hooks(EventHandler())
    plugin.bot.d.lavalink = client

    youtube = build('youtube', 'v3', static_discovery=False, developerKey=os.environ["YOUTUBE_API_KEY"])
    plugin.bot.d.youtube = youtube
    plugin.bot.d.spotify = SpotifyClient()


@plugin.command()
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("query", "The query to search for.", modifier=lightbulb.OptionModifier.CONSUME_REST, required=True)
@lightbulb.command("play", "Searches the query on youtube, or adds the URL to the queue.", auto_defer = True)
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def play(ctx: lightbulb.Context) -> None:
    """Searches the query on youtube, or adds the URL to the queue."""

    query = ctx.options.query
    await MusicClient(plugin)._play(ctx, query)


@plugin.command()
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("leave", "Leaves the voice channel the bot is in, clearing the queue.")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def leave(ctx: lightbulb.Context) -> None:
    """Leaves the voice channel the bot is in, clearing the queue."""

    if not await MusicClient(plugin)._leave(ctx.guild_id):
        await ctx.respond(":warning: Bot is not currently in any voice channel!")
    else:
        await ctx.respond("Left voice channel")
        

@plugin.command()
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("join", "Joins the voice channel you are in.")
@lightbulb.implements(lightbulb.SlashCommand)
async def join(ctx: lightbulb.Context) -> None:
    channel_id = await MusicClient(plugin)._join(ctx)

    if channel_id:
        await ctx.respond(f"Joined <#{channel_id}>")


@plugin.command()
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("stop", "Stops the current song and clears queue.")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def stop(ctx: lightbulb.Context) -> None:
    """Stops the current song (skip to continue)."""

    player = plugin.bot.d.lavalink.player_manager.get(ctx.guild_id)
    
    if not player:
        await ctx.respond(":warning: Nothing to stop")
        return 
    
    player.queue.clear()
    await player.stop()

    await ctx.respond(
        embed = hikari.Embed(
            description = ":stop_button: Stopped playing",
            colour = 0xd25557
        )
    )

@plugin.command()
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("skip", "Skips the current song.")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def skip(ctx: lightbulb.Context) -> None:
    """Skips the current song."""

    player = plugin.bot.d.lavalink.player_manager.get(ctx.guild_id)

    if not player or not player.is_playing:
        await ctx.respond(":warning: Nothing to skip")
    else:
        cur_track = player.current
        await player.play()

        await ctx.respond(
            embed = hikari.Embed(
                description = f":fast_forward: Skipped: [{cur_track.title}]({cur_track.uri})",
                colour = 0xd25557
            )
        )

@plugin.command()
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("pause", "Pauses the current song.")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def pause(ctx: lightbulb.Context) -> None:
    """Pauses the current song."""

    player = plugin.bot.d.lavalink.player_manager.get(ctx.guild_id)

    if not player or not player.is_playing:
        await ctx.respond(":warning: Player is not currently playing!")
        return
    await player.set_pause(True)
    await ctx.respond(
        embed = hikari.Embed(
            description = ":pause_button: Paused player",
            colour = 0xf9c62b
        )
    )

@plugin.command()
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("resume", "Resumes playing the current song.")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def resume(ctx: lightbulb.Context) -> None:
    """Resumes playing the current song."""

    player = plugin.bot.d.lavalink.player_manager.get(ctx.guild_id)
    if player and player.paused:
        await player.set_pause(False)
    else:
        await ctx.respond(":warning: Player is not currently paused!")
        return

    await ctx.respond(
        embed = hikari.Embed(
            description = ":arrow_forward: Resumed player",
            colour = 0x76ffa1
        )
    )

@plugin.command()
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("queue", "Shows the next 10 songs in the queue", aliases = ['q'])
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def queue(ctx : lightbulb.Context) -> None:

    player = plugin.bot.d.lavalink.player_manager.get(ctx.guild_id)

    if not player or not player.is_playing:
        await ctx.respond(":warning: Player is not currently playing")
        return 
    
    length = divmod(player.current.duration, 60000)
    queueDescription = f"**Current:** [{player.current.title}]({player.current.uri}) `{int(length[0])}:{round(length[1]/1000):02}` [<@!{player.current.requester}>]"
    i = 0
    while i < len(player.queue) and i < 10:
        if i == 0: 
            queueDescription += '\n\n' + '**Up next:**'
        length = divmod(player.queue[i].duration, 60000)
        queueDescription = queueDescription + '\n' + f"[{i + 1}. {player.queue[i].title}]({player.queue[i].uri}) `{int(length[0])}:{round(length[1]/1000):02}` [<@!{player.queue[i].requester}>]"
        i += 1

    queueEmbed = hikari.Embed(
        title = "🎶 Queue",
        description = queueDescription,
        colour = 0x76ffa1,
    )

    await ctx.respond(embed=queueEmbed)


@plugin.command()
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("chill", "Play random linhnhichill", auto_defer = True)
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def chill(ctx: lightbulb.Context) -> None:

    BASE_YT_URL = 'https://www.youtube.com/watch'
    query = None

    rand_vid = -1
    next_page_token = None
    while True:
        res = plugin.bot.d.youtube.playlistItems().list(
            playlistId='PL-F2EKRbzrNS0mQqAW6tt75FTgf4j5gjS',  # linhnhichill's playlist ID
            part='snippet',
            pageToken = next_page_token,
            maxResults=50
        ).execute()

        if rand_vid == -1:
            rand_vid = random.randint(0, res['pageInfo']['totalResults'])
        if rand_vid < 50:
            vid_id = res['items'][rand_vid]['snippet']['resourceId']['videoId']  # id
            query = f"{BASE_YT_URL}?v={vid_id}" 
            break

        rand_vid -= 50
        next_page_token = res.get('nextPageToken')

    assert query is not None
    await MusicClient(plugin)._play(ctx, query)


@plugin.listener(hikari.VoiceServerUpdateEvent)
async def voice_server_update(event: hikari.VoiceServerUpdateEvent) -> None:

    lavalink_data = {
        't': 'VOICE_SERVER_UPDATE',
        'd': {
            'guild_id': event.guild_id,
            'endpoint': event.endpoint[6:],  # get rid of wss://
            'token': event.token,
        }
    }

    await plugin.bot.d.lavalink.voice_update_handler(lavalink_data)


@plugin.listener(hikari.VoiceStateUpdateEvent)
async def voice_state_update(event: hikari.VoiceStateUpdateEvent) -> None:

    prev_state = event.old_state
    cur_state = event.state

    # send event update to lavalink server
    lavalink_data = {
        't': 'VOICE_STATE_UPDATE',
        'd': {
            'guild_id': cur_state.guild_id,
            'user_id': cur_state.user_id,
            'channel_id': cur_state.channel_id,
            'session_id': cur_state.session_id,
        }
    }

    await plugin.bot.d.lavalink.voice_update_handler(lavalink_data)

    bot_id = plugin.bot.get_me().id
    bot_voice_state = plugin.bot.cache.get_voice_state(cur_state.guild_id, bot_id)

    if not bot_voice_state or cur_state.user_id == bot_id:
        return

    states = plugin.bot.cache.get_voice_states_view_for_guild(cur_state.guild_id).items()
    
    # count users in channel with bot
    cnt_user = len([state[0] for state in filter(lambda i: i[1].channel_id == bot_voice_state.channel_id, states)])

    if cnt_user == 1:  # only bot left in voice
        await MusicClient(plugin)._leave(cur_state.guild_id)
        return
    if cnt_user > 2:  # not just bot & lone user
        return
    
    # resume player when user undeafens
    if prev_state.is_self_deafened and not cur_state.is_self_deafened:

        player = plugin.bot.d.lavalink.player_manager.get(cur_state.guild_id)
        if player and player.paused:
            await player.set_pause(False)
        else:
            return

        logging.info("Track resumed on guild: %s", event.guild_id)
    
    # pause player when user deafens
    if not prev_state.is_self_deafened and cur_state.is_self_deafened:
        
        player = plugin.bot.d.lavalink.player_manager.get(cur_state.guild_id)
        if not player or not player.is_playing:
            return
        
        await player.set_pause(True)
        logging.info("Track paused on guild: %s", event.guild_id)


def load(bot: lightbulb.BotApp) -> None:
    bot.add_plugin(plugin)