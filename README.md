# Born Here, Playing There: FIFA Nationality Paradox

As I watched FIFA World Cup Soccer game after game I could not help but wonder why many players do not appear to belong to the country they are playing for. Of course, saying so publicly would be politically incorrect. Moreover, as an immigrant to the US, how dare I stereotype. Nevertheless, I couldn't help myself, so I dug deeper. With assistance from Claude Sonnet 4.6, I gathered Football player data from Football API (https://www.api-football.com) and determined player country of birth and inferred citizenship from their Wikipedia pages (https://www.wikipedia.org/). There are 52 playing nations with 24 players in each team for a total of 1248 players. Of these, birth country was not available for 315 players and citizenship was not available for 308. When one examines data on the 933 players for whom complete data was obtained, an interesting picture emerges: 213 (22.8%) of players are born in a different country from the one they are playing for and 283 (30.3%) of players are citizens (or dual citizens) of a different country.

FIFA rules allow a player to represent a specific country if they meet at least one of the following four conditions: born there, parents or grandparents were born there, or player has lived there continuously for at least five years. When the option is available players tend to choose the country that gives them the best shot of playing in the World Cup. Good for the players but to the country it may look like they are exporting talent.

## Visualizations

### Crossing Borders: Born in One Country, Representing Another
![FIFA World Cup 2026 Migration](wc2026_migration.png)

### Citizenship Paradox: Citizenship of One Country, Representing Another
![FIFA World Cup 2026 Citizenship](wc2026_citizenship.png)

## Interactive Versions (GitHub Pages)
You can view the interactive, hoverable versions of these charts directly in your browser:
* [Interactive Migration Flow Chart](https://pseudorational.github.io/fifa-nationality-paradox/wc2026_migration.html)
* [Interactive Citizenship Flow Chart](https://pseudorational.github.io/fifa-nationality-paradox/wc2026_citizenship.html)
