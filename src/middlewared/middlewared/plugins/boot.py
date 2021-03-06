import os
import tempfile

from middlewared.schema import Bool, Dict, Int, Str, accepts
from middlewared.service import CallError, Service, job, private
from middlewared.utils import run

from bsd import geom


class BootService(Service):

    async def get_state(self):
        """
        Returns the current state of the boot pool, including all vdevs, properties and datasets.
        """
        return await self.middleware.call('zfs.pool.query', [('name', '=', 'freenas-boot')], {'get': True})

    @accepts()
    async def get_disks(self):
        """
        Returns disks of the boot pool.
        """
        return await self.middleware.call('zfs.pool.get_disks', 'freenas-boot')

    @private
    async def get_boot_type(self):
        """
        Get the boot type of the boot pool.

        Returns:
            "BIOS", "EFI", None
        """
        await self.middleware.run_in_thread(geom.scan)
        labelclass = geom.class_by_name('PART')
        efi = bios = 0
        async for disk in await self.get_disks():
            for e in labelclass.xml.findall(f".//geom[name='{disk}']/provider/config/type"):
                if e.text == 'efi':
                    efi += 1
                elif e.text == 'bios-boot':
                    bios += 1
        if efi == 0 and bios == 0:
            return None
        if bios > 0:
            return 'BIOS'
        return 'EFI'

    @accepts(
        Str('dev'),
        Dict(
            'options',
            Int('size'),
        )
    )
    @private
    async def format(self, dev, options):
        """
        Format a given disk `dev` using the appropiate partition layout
        """

        job = await self.middleware.call('disk.wipe', dev, 'QUICK')
        await job.wait()

        commands = []
        commands.append(['gpart', 'create', '-s', 'gpt', '-f', 'active', f'/dev/{dev}'])
        boottype = await self.get_boot_type()
        if boottype == 'EFI':
            commands.append(['gpart', 'add', '-t', 'efi', '-i', '1', '-s', '260m', dev])
            commands.append(['newfs_msdos', '-F', '16', f'/dev/{dev}p1'])
        else:
            commands.append(['gpart', 'add', '-t', 'freebsd-boot', '-i', '1', '-s', '512k', dev])
            commands.append(['gpart', 'set', '-a', 'active', dev])
        commands.append(
            ['gpart', 'add', '-t', 'freebsd-zfs', '-i', '2', '-a', '4k'] + (
                ['-s', str(options['size']) + 'B'] if options.get('size') else []
            ) + [dev]
        )
        for command in commands:
            p = await run(*command, check=False)
            if p.returncode != 0:
                raise CallError('%r failed:\n%s%s' % (" ".join(command), p.stdout.decode("utf-8"), p.stderr.decode("utf-8")))

        return boottype

    @private
    async def install_loader(self, boottype, dev):
        if boottype == 'EFI':
            with tempfile.TemporaryDirectory() as tmpdirname:
                await run('mount', '-t', 'msdosfs', f'/dev/{dev}p1', tmpdirname, check=False)
                try:
                    os.makedirs(f'{tmpdirname}/efi/boot')
                except FileExistsError:
                    pass
                await run('cp', '/boot/boot1.efi', f'{tmpdirname}/efi/boot/BOOTx64.efi', check=False)
                await run('umount', tmpdirname, check=False)

        else:
            await run('gpart', 'bootcode', '-b', '/boot/pmbr', '-p', '/boot/gptzfsboot', '-i', '1', f'/dev/{dev}', check=False)

    @accepts(
        Str('dev'),
        Dict(
            'options',
            Bool('expand', default=False),
        ),
    )
    @job(lock='boot_attach')
    async def attach(self, job, dev, options=None):
        """
        Attach a disk to the boot pool, turning a stripe into a mirror.

        `expand` option will determine whether the new disk partition will be
                 the maximum available or the same size as the current disk.
        """

        disks = [d async for d in await self.get_disks()]
        if len(disks) > 1:
            raise CallError('3-way mirror not supported yet')

        format_opts = {}
        if not options['expand']:
            # Lets try to find out the size of the current freebsd-zfs partition so
            # the new partition is not bigger, preventing size mismatch if one of
            # them fail later on. See #21336
            await self.middleware.run_in_thread(geom.scan)
            labelclass = geom.class_by_name('PART')
            for e in labelclass.xml.findall(f"./geom[name='{disks[0]}']/provider/config[type='freebsd-zfs']"):
                format_opts['size'] = int(e.find('./length').text)
                break

        try:
            boottype = await self.format(dev, format_opts)
        except CallError as e:
            if "gpart: autofill: No space left on device" in e.errmsg:
                async def get_diskinfo(dev):
                    diskinfo = {
                        s.split("#")[1].strip(): s.split("#")[0].strip()
                        for s in (await run("/usr/sbin/diskinfo", "-v", dev)).stdout.decode("utf-8").split("\n")
                        if "#" in s
                    }
                    return {
                        "name": diskinfo.get("Disk descr.", dev),
                        "size_gb": "%.2f" % ((int(diskinfo["mediasize in sectors"]) * int(diskinfo["sectorsize"]) /
                                             float(1024 ** 3))),
                        "size_sectors": int(diskinfo["mediasize in sectors"]),
                    }

                src_info = await get_diskinfo(disks[0])
                dst_info = await get_diskinfo(dev)

                raise CallError((
                    f"The device called {dst_info['name']} ({dst_info['size_gb']} GB, {dst_info['size_sectors']} "
                    f"sectors does not have enough space to mirror the old device {src_info['name']} "
                    f"({src_info['size_gb']} GB, {src_info['size_sectors']} sectors). Please use a larger device."
                ))

            raise

        await self.middleware.call('zfs.pool.extend', 'freenas-boot', None, [{'target': f'{disks[0]}p2', 'type': 'DISK', 'path': f'/dev/{dev}p2'}])

        await self.install_loader(boottype, dev)

    @accepts(Str('dev'))
    async def detach(self, dev):
        """
        Detach given `dev` from boot pool.
        """
        await self.middleware.call('zfs.pool.detach', 'freenas-boot', dev)

    @accepts(Str('label'), Str('dev'))
    async def replace(self, label, dev):
        """
        Replace device `label` on boot pool with `dev`.
        """
        boottype = await self.format(dev)
        await self.middleware.call('zfs.pool.replace', 'freenas-boot', label, f'{dev}p2')
        await self.install_loader(boottype, dev)

    @accepts()
    @job(lock='boot_scrub')
    async def scrub(self, job):
        """
        Scrub on boot pool.
        """
        subjob = await self.middleware.call('zfs.pool.scrub', 'freenas-boot')
        return await job.wrap(subjob)
