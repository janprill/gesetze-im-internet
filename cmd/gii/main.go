package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/janprill/gii"
)

func main() {
	if err := run(context.Background(), os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(ctx context.Context, args []string) error {
	if len(args) == 0 {
		usage(os.Stderr)
		return flag.ErrHelp
	}
	switch args[0] {
	case "text":
		return runText(ctx, args[1:])
	case "update":
		return runUpdate(ctx, args[1:])
	case "init":
		return runInit(ctx, args[1:])
	case "help", "--help", "-h":
		usage(os.Stdout)
		return nil
	default:
		usage(os.Stderr)
		return fmt.Errorf("unknown command %q", args[0])
	}
}

func runText(ctx context.Context, args []string) error {
	fs := flag.NewFlagSet("gii text", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	common := addCommonFlags(fs)
	dateValue := fs.String("date", "", "Stichtag im Format YYYY-MM-DD; default: heute")
	todayValue := fs.String("today", "", "Test-/Automationshilfe: heutiges Datum im Format YYYY-MM-DD")
	noUpdate := fs.Bool("no-update", false, "lokalen Cache verwenden, ohne vorher zu fetchen")
	if err := fs.Parse(flagsFirst(args)); err != nil {
		return err
	}
	if fs.NArg() != 1 {
		return fmt.Errorf("usage: gii text <gesetz> [--date YYYY-MM-DD]")
	}
	clock, err := clockFromToday(*todayValue)
	if err != nil {
		return err
	}
	client := gii.New(common.options(clock))
	date, err := parseOptionalDate(*dateValue)
	if err != nil {
		return err
	}
	var law *gii.Law
	if *noUpdate {
		law, err = client.LawTextWithoutUpdate(ctx, fs.Arg(0), date)
	} else {
		law, err = client.LawText(ctx, fs.Arg(0), date)
	}
	if err != nil {
		return err
	}
	fmt.Print(law.Text)
	return nil
}

func runUpdate(ctx context.Context, args []string) error {
	fs := flag.NewFlagSet("gii update", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	common := addCommonFlags(fs)
	if err := fs.Parse(args); err != nil {
		return err
	}
	if fs.NArg() != 0 {
		return fmt.Errorf("usage: gii update [flags]")
	}
	client := gii.New(common.options(nil))
	return client.Update(ctx)
}

func runInit(ctx context.Context, args []string) error {
	fs := flag.NewFlagSet("gii init", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	common := addCommonFlags(fs)
	if err := fs.Parse(args); err != nil {
		return err
	}
	if fs.NArg() != 0 {
		return fmt.Errorf("usage: gii init [--repo-dir ./.gii-data]")
	}
	if *common.repoDir == "" {
		*common.repoDir = ".gii-data"
	}
	client := gii.New(common.options(nil))
	return client.Update(ctx)
}

type commonFlags struct {
	dataRepo *string
	repoURL  *string
	cacheDir *string
	repoDir  *string
	branch   *string
	gitBin   *string
}

func addCommonFlags(fs *flag.FlagSet) commonFlags {
	return commonFlags{
		dataRepo: fs.String("data-repo", "", "Git repository URL with data branch (default: "+gii.DefaultRepositoryURL+")"),
		repoURL:  fs.String("repo-url", "", "Deprecated alias for --data-repo"),
		cacheDir: fs.String("cache-dir", "", "Cache directory; clone lives below <cache-dir>/repo (default: OS user cache dir)"),
		repoDir:  fs.String("repo-dir", "", "Explicit local data repository directory, e.g. ./.gii-data"),
		branch:   fs.String("branch", "", "Data branch name (default: "+gii.DefaultDataBranch+")"),
		gitBin:   fs.String("git", "", "Git executable (default: git)"),
	}
}

func (f commonFlags) options(clock func() time.Time) gii.Options {
	repositoryURL := *f.dataRepo
	if repositoryURL == "" {
		repositoryURL = *f.repoURL
	}
	return gii.Options{
		RepositoryURL: repositoryURL,
		CacheDir:      *f.cacheDir,
		RepositoryDir: *f.repoDir,
		DataBranch:    *f.branch,
		GitBin:        *f.gitBin,
		Clock:         clock,
	}
}

func parseOptionalDate(value string) (time.Time, error) {
	if value == "" {
		return time.Time{}, nil
	}
	return time.Parse("2006-01-02", value)
}

func flagsFirst(args []string) []string {
	stringFlags := map[string]bool{
		"date": true, "today": true, "data-repo": true, "repo-url": true, "cache-dir": true, "repo-dir": true, "branch": true, "git": true,
	}
	var flags, positional []string
	for i := 0; i < len(args); {
		arg := args[i]
		if !strings.HasPrefix(arg, "-") || arg == "-" {
			positional = append(positional, arg)
			i++
			continue
		}
		flags = append(flags, arg)
		name := strings.TrimLeft(arg, "-")
		if cut, _, ok := strings.Cut(name, "="); ok {
			name = cut
		}
		if stringFlags[name] && !strings.Contains(arg, "=") && i+1 < len(args) {
			flags = append(flags, args[i+1])
			i += 2
			continue
		}
		i++
	}
	return append(flags, positional...)
}

func clockFromToday(value string) (func() time.Time, error) {
	if value == "" {
		return nil, nil
	}
	parsed, err := time.Parse("2006-01-02", value)
	if err != nil {
		return nil, err
	}
	return func() time.Time { return parsed }, nil
}

func usage(out *os.File) {
	fmt.Fprintln(out, `gii - Gesetze-im-Internet data-branch CLI

Usage:
  gii init [--repo-dir ./.gii-data] [--data-repo URL] [--branch data]
  gii update [--data-repo URL] [--cache-dir DIR | --repo-dir DIR] [--branch data]
  gii text <gesetz> [--date YYYY-MM-DD] [--data-repo URL] [--cache-dir DIR | --repo-dir DIR] [--branch data] [--no-update]

Examples:
  gii init --repo-dir ./.gii-data
  gii text BGB --date 2024-02-15
  gii text "Bürgerliches Gesetzbuch"
  gii update --data-repo https://github.com/QuantLaw/gesetze-im-internet.git`)
}
