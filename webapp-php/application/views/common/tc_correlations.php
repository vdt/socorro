<?php if ($crasher->{'display_signature'} == Crash::$empty_sig || $crasher->{'display_signature'} == Crash::$null_sig) { ?>
    <td>N/A</td>
<?php } else { ?>
    <td class="correlation-cell">
        <div id="correlation-panel<?= $row ?>">
            <div class="top"><span></span></div><a class="correlation-toggler" href="#">Show More</a>
                <div class="complete">
                <h3>Based on <span class='osname'><?= $crasher->{'correlation_os'} ?></span> crashes</h3>
                <div class="correlation-module"><h3>CPU</h3><div class="cpus"></div></div>
                <div class="correlation-module"><h3>Add-ons</h3><div class="addons"></div></div>
                <div class="correlation-module"><h3>Modules</h3><div class="modules"></div></div>
            </div>
        </div>
    </td>
<?php } ?>