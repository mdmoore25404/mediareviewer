# media reviewer

media reviewer is intended to be an easy low resource responsive mobile-friendly webapp for reviewing images and video clips to determine if the files should be deleted, kept, etc. 

Use case exmaple reviwing many media items from trail cameras or photoshoots to keep/delete.

## tech stack

- Python Flask API in its own venv
- vite reactjs + bootstrap + fontawesome resposnive webapp mobile-first.
- can build as a docker image
  - great use case is to run it via docker on a NAS device.
  - when run as a docker image the api and reactjs frontend should serve from the same host:port and use path to know where to send the request e.g. /api goes to the api /anythingelse goes to react.
- automatic linting and testing

## features

- runs as normal user no root needed
- no separate database required utilizes companion sibling files to indicate status
  - `{filename}.lock` prevents deletion of `{filename}` via the ui
  - `{filename}.trash` indicates the file is flagged for deletion
  - `{filename}.seen` indicates it was seen in the ui
  - `.lock` and `.trash` are mutually exclusive. it is not possible via the app to create a `.lock` for a `.trash` and vice versa.
  - can mark a file as unseen by removing the `.seen` companion file.
- Add folders to review via the webui. 
  - if the user the process runs as can see it.
  - can configure paths that are hidden from the folder picker
  - the active paths available for quick review are tracked via a text file in the process owners homedir (~/.mediareviewer contains settings)
- media items can be deleted (marked for trash)
  - a separate emtpy trash command in the scope of a review folder will locate the `.trash` files recursively and delete the file and existing companion files (.seen .trash)  
  - the deletion is an async process, the api queues up and dispatches to a thread/process to efficiently remove the files requested.
  - the active deletion processes can be tracked via the ui and cancelled if needed.
- thumbnail and list views with clear indication of locked trashed seen.
- filtering based on 
    - locked/trashed/seen
    - media type (movie/still)
    - media size
- sorting based on
    - locked/trashed/seen
    - media size
    - modified date
    - created date
- customizeable share  (stretch goal)
  - imgur/trailcam.online/frenpost.xyz/facebook/instagram/etc/etc

### review mode
- The review mode will show a media item using the full browser display, adjusted to fit the screen.
- movie files will auto play with sound
- buttons with icons to allow `lock` `trash` actions as well as `unseen`
  - selecting lock trash or unseen actions will make the flag and automatically move to the next item 
- forward/back buttons 


###