export interface ChangelogEntry {
  version: string
  date: string
  highlights: string[]
}

export const CHANGELOG: ChangelogEntry[] = [
  {
    version: 'Unreleased',
    date: '',
    highlights: [
      'Added a "What\'s new" section to the About tab so you can see release notes without leaving the app.',
    ],
  },
  {
    version: '0.4.0',
    date: '2026-04-10',
    highlights: [
      'New About tab in Settings shows version numbers, the GitHub link and public data sources.',
      'Last.fm queue panel lets you select, retry or delete pending scrobbles individually.',
      'Track trivia (Last.fm, MusicBrainz, Wikipedia) is now cached for up to a week with a manual clear button.',
    ],
  },
  {
    version: '0.3.0',
    date: '2026-03-12',
    highlights: [
      'Favorites sync between Spotify and Last.fm with conflict resolution.',
      'Background sync interval is configurable per account.',
      'Custom display name option in the Connections tab.',
    ],
  },
  {
    version: '0.2.0',
    date: '2026-02-04',
    highlights: [
      'Playlist recipes with sort key chaining and live previews.',
      'Recently used playlists panel for one-click access.',
      'Track detail panel with cross-provider trivia.',
    ],
  },
  {
    version: '0.1.0',
    date: '2026-01-15',
    highlights: [
      'Initial Pigify release with Spotify login and basic playlist browsing.',
    ],
  },
]
